"use client";

import React, { useState, useEffect, useRef } from 'react';
import { Bot, User, Paperclip, Send } from 'lucide-react';

import { useRouter, useSearchParams } from 'next/navigation';
import { fetchWithAuth, getApiUrl } from '../../app/lib/api';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
  id: string | number;
  role: 'user' | 'assistant';
  content: string;
}

interface ChatTitleUpdatedDetail {
  chatId: number;
  title: string;
  createdAt?: string;
}

export default function ChatArea() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [chatTitle, setChatTitle] = useState('Loading...');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const router = useRouter();
  const searchParams = useSearchParams();
  const chatIdParam = searchParams.get('chatId');
  const isNewChat = chatIdParam === 'new';
  const chatId = isNewChat ? 'new' : (chatIdParam ? parseInt(chatIdParam, 10) : null);

  const isCreatingNewChat = useRef(false);
  const dispatchChatTitleUpdated = (detail: ChatTitleUpdatedDetail) => {
    window.dispatchEvent(new CustomEvent<ChatTitleUpdatedDetail>('chat-title-updated', { detail }));
  };

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Proper auth and chat init
  useEffect(() => {
    const init = async () => {
      try {
        const apiUrl = getApiUrl();
        
        // If no chatId in URL, fetch chats and redirect to the first one or create new
        if (!chatIdParam) {
          const activeWsId = localStorage.getItem('motifold_active_workspace_id');
          const wsQuery = activeWsId ? `?workspace_id=${activeWsId}` : '';
          const chatsRes = await fetchWithAuth(`${apiUrl}/chats/${wsQuery}`);

          if (chatsRes.status === 401) {
            // fetchWithAuth already handles redirect to login if refresh fails
            return;
          }

          if (chatsRes.ok) {
            const chatsData = await chatsRes.json();
            const chats = Array.isArray(chatsData) ? chatsData : chatsData.items ?? [];
            if (chats.length > 0) {
              router.replace(`/?chatId=${chats[0].id}`);
            } else {
              router.replace(`/?chatId=new`);
            }
          }
          return;
        }

        if (isNewChat) {
          setMessages([]);
          setChatTitle('New Chat');
          return;
        }

        if (isCreatingNewChat.current) {
          isCreatingNewChat.current = false;
          return;
        }

        // Reset state when switching chats
        setMessages([]);
        setChatTitle('Loading...');

        // Fetch chat details for title
        const chatRes = await fetchWithAuth(`${apiUrl}/chats/${chatId}`);
        if (chatRes.ok) {
          const chatData = await chatRes.json();
          setChatTitle(chatData.title);
        }

        // Fetch messages for chat
        const msgRes = await fetchWithAuth(`${apiUrl}/chats/${chatId}/messages`);
        
        if (msgRes.ok) {
          const msgData = await msgRes.json();
          const initialMessages = Array.isArray(msgData) ? msgData : msgData.items ?? [];
          setMessages(initialMessages);
        }
      } catch (e) {
        console.error("Initialization failed:", e);
      }
    };
    
    init();
  }, [chatIdParam, chatId, isNewChat, router]);
  const sendMessage = async () => {
    if (!input.trim() || !chatId || isLoading) return;

    const userMessageContent = input.trim();
    setInput('');
    setIsLoading(true);

    const apiUrl = getApiUrl();
    
    // Optimistic UI update
    const tempUserId = Date.now();
    setMessages(prev => [...prev, { id: tempUserId, role: 'user', content: userMessageContent }]);

    try {
      let actualChatId = chatId;
      if (chatId === 'new') {
        isCreatingNewChat.current = true;
        const activeWsId = localStorage.getItem('motifold_active_workspace_id');
        const createBody: { workspace_id?: number } = {};
        if (activeWsId) {
          createBody.workspace_id = parseInt(activeWsId, 10);
        }
        
        const createRes = await fetchWithAuth(`${apiUrl}/chats/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(createBody)
        });
        if (!createRes.ok) throw new Error("Failed to create chat");
        const newChat = await createRes.json();
        actualChatId = newChat.id;
        
        dispatchChatTitleUpdated({
          chatId: newChat.id,
          title: newChat.title || 'New Chat',
          createdAt: newChat.created_at
        });
        router.replace(`/?chatId=${actualChatId}`);
      }

      const resolvedChatId = typeof actualChatId === 'number' ? actualChatId : parseInt(actualChatId, 10);

      const idempotencyKey = `msg_${Date.now()}_${Math.random()}`;
      
      const res = await fetchWithAuth(`${apiUrl}/chats/${resolvedChatId}/messages`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content: userMessageContent,
          idempotency_key: idempotencyKey
        })
      });

      if (res.status === 401) {
        return; // Already handled by fetchWithAuth
      }

      if (!res.ok) throw new Error("Failed to send message");

      // Setup SSE for stream
      const streamUrl = `${apiUrl}/chats/${resolvedChatId}/stream`;
        
      const eventSource = new EventSource(streamUrl, { withCredentials: true });
      
      let assistantMessageContent = '';
      const tempAssistantId = Date.now() + 1;
      
      setMessages(prev => [...prev, { id: tempAssistantId, role: 'assistant', content: '...' }]);

      eventSource.addEventListener('title', (event) => {
        const messageEvent = event as MessageEvent<string>;
        let nextTitle = messageEvent.data;

        try {
          if (nextTitle.startsWith('"') && nextTitle.endsWith('"')) {
            nextTitle = JSON.parse(nextTitle);
          }
        } catch (e) {
          console.warn("Failed to parse title event", e);
        }

        if (!nextTitle) {
          return;
        }

        setChatTitle(nextTitle);
        dispatchChatTitleUpdated({ chatId: resolvedChatId, title: nextTitle });
      });

      eventSource.onmessage = (event) => {
        if (event.data === '[DONE]') {
          eventSource.close();
          setIsLoading(false);
          
          // Refetch title if it was "New Chat"
          if (chatTitle === 'New Chat' || chatTitle === 'Loading...') {
            fetchWithAuth(`${apiUrl}/chats/${resolvedChatId}`)
            .then(res => res.json())
            .then(data => {
              if (data.title && data.title !== 'New Chat') {
                setChatTitle(data.title);
                dispatchChatTitleUpdated({
                  chatId: resolvedChatId,
                  title: data.title,
                  createdAt: data.created_at
                });
              }
            })
            .catch(console.error);
          }
          return;
        }
        
        try {
          const rawData = event.data;
          let text = rawData;
          try {
            // Try to parse if it's JSON encoded (to handle newlines correctly)
            if (rawData.startsWith('"') && rawData.endsWith('"')) {
              text = JSON.parse(rawData);
            }
          } catch (e) {
            console.warn("Failed to parse JSON token", e);
          }
          
          if (assistantMessageContent === '' && text !== '') {
            // Remove the initial '...' when first real token arrives
            assistantMessageContent = text;
          } else {
            assistantMessageContent += text;
          }
          
          setMessages(prev => prev.map(msg => 
            msg.id === tempAssistantId ? { ...msg, content: assistantMessageContent } : msg
          ));
        } catch (e) {
          console.error("Error parsing SSE data", e);
        }
      };

      eventSource.onerror = (error) => {
        if (eventSource.readyState === EventSource.CLOSED) {
          return;
        }
        console.error("SSE Error", error);
        eventSource.close();
        setIsLoading(false);
      };

    } catch (e) {
      console.error("Failed to send message", e);
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <main className="flex-1 flex flex-col bg-white min-w-0 relative">
      {/* Background Pattern */}
      <div 
        className="absolute inset-0 z-0 opacity-[0.02] pointer-events-none" 
        style={{ backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }}
      ></div>
      
      <div className="relative z-10 flex-1 flex flex-col h-full">
        {/* Chat Header */}
        <div className="h-16 border-b border-slate-100 flex items-center px-6 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center">
              <Bot className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800">{chatTitle}</h3>
            </div>
          </div>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* System Message */}
          <div className="flex justify-center">
            <div className="bg-slate-100 text-slate-500 text-xs px-3 py-1 rounded-full">
              今天 {new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
            </div>
          </div>

          {messages.map((msg, index) => (
            <div key={msg.id || index} className={`flex gap-4 max-w-4xl mx-auto ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              {/* Avatar */}
              <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-slate-800 text-white' : 'bg-indigo-600 text-white'}`}>
                {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>
              
              {/* Content Bubble */}
              <div className={`flex flex-col gap-1 max-w-[80%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                <div className="text-xs text-slate-400 px-1">{msg.role === 'user' ? '你' : 'Motifold'}</div>
                <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm ${msg.role === 'user' ? 'bg-indigo-600 text-white rounded-tr-sm' : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm'}`}>
                  {msg.role === 'user' ? (
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  ) : (
                    <div className="prose prose-sm prose-slate max-w-none prose-p:leading-relaxed prose-pre:bg-slate-800 prose-pre:text-slate-100 prose-a:text-indigo-600 prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Chat Input */}
        <div className="p-4 bg-white border-t border-slate-100">
          <div className="max-w-4xl mx-auto relative shadow-sm border border-slate-200 rounded-2xl bg-white focus-within:border-indigo-500 focus-within:ring-4 focus-within:ring-indigo-500/10 transition-all duration-200">
            <textarea 
              className="w-full bg-transparent p-4 pr-16 resize-none outline-none text-sm text-slate-700 min-h-[60px] max-h-[200px]" 
              placeholder="输入指令，或者 @提及 模块..."
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading || !chatId}
            ></textarea>
            <div className="absolute bottom-3 right-3 flex items-center gap-2">
              <button className="text-slate-400 hover:text-indigo-500 p-1 transition-colors">
                <Paperclip className="w-4 h-4" />
              </button>
              <button 
                className={`w-8 h-8 rounded-xl flex items-center justify-center shadow-md transition-colors ${
                  !input.trim() || isLoading || !chatId
                    ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                    : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                }`}
                onClick={sendMessage}
                disabled={!input.trim() || isLoading || !chatId}
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
