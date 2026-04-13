"use client";

import { useEffect, useState } from "react";
import { Bell, X, CheckCircle, AlertCircle } from "lucide-react";

interface NotificationEvent {
  type: string;
  task_type: string;
  resource_type: string;
  resource_id: number;
  result: string;
  status: string;
  title: string;
  message: string;
  link?: string;
}

export default function GlobalNotification() {
  const [notifications, setNotifications] = useState<(NotificationEvent & { id: string })[]>([]);

  useEffect(() => {
    // We only connect if we are not on the login page
    const isLoginPage = typeof window !== 'undefined' && window.location.pathname.startsWith('/login');
    if (isLoginPage) return;

    const streamUrl = '/notifications/stream';
    let aborted = false;
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;

    let connectAttempts = 0;

    const connect = async () => {
      if (aborted) return;

      try {
        const response = await fetch(streamUrl, {
          credentials: 'include',
        });

        if (!response.ok) {
          if (response.status === 401) {
            // Let page-level auth own redirects; don't start a navigation loop from SSE.
            return;
          }
          throw new Error(`SSE connection failed: ${response.status}`);
        }

        if (!response.body) {
          throw new Error('No response body');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        const readStream = () => {
          reader.read().then(({ done, value }) => {
            if (done || aborted) {
              if (!aborted) {
                // Connection closed, try to reconnect after a delay
                retryTimeout = setTimeout(connect, 3000);
              }
              return;
            }

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6)) as NotificationEvent;

                  // Basic payload filtering
                  if (!data.title || !data.message || !data.resource_type) {
                    return;
                  }

                  const newNotif = { ...data, id: Date.now().toString() };

                  // Show in-app toast
                  setNotifications(prev => [...prev, newNotif]);

                  // Dispatch event for other components
                  window.dispatchEvent(new CustomEvent('global-notification', { detail: data }));

                  // Browser Native Notification if tab is hidden
                  if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
                    const notification = new Notification(data.title, { body: data.message });
                    if (data.link) {
                      notification.onclick = () => {
                        window.focus();
                        window.location.href = data.link!;
                      };
                    }
                  }

                  // Auto remove after 5 seconds
                  setTimeout(() => {
                    setNotifications(prev => prev.filter(n => n.id !== newNotif.id));
                  }, 5000);
                } catch (e) {
                  console.warn("Failed to parse notification", e);
                }
              }
            }

            if (!aborted) {
              readStream();
            }
          }).catch((err) => {
            if (!aborted) {
              console.warn("Notification SSE read error, reconnecting...", err);
              retryTimeout = setTimeout(connect, 3000);
            }
          });
        };

        readStream();
      } catch (err) {
        if (!aborted) {
          // Only log on subsequent retries, not initial attempts (auth may not be ready)
          if (connectAttempts > 0) {
            console.warn("Notification SSE connection error, retrying...", err);
          }
          connectAttempts++;
          retryTimeout = setTimeout(connect, 3000);
        }
      }
    };

    // Delay initial connection to avoid race condition with auth on page load
    const initialDelay = setTimeout(connect, 1000);

    return () => {
      aborted = true;
      if (retryTimeout) {
        clearTimeout(retryTimeout);
      }
      clearTimeout(initialDelay);
    };
  }, []);

  const removeNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const handleNotificationClick = (notif: NotificationEvent & { id: string }) => {
    if (notif.link) {
      window.location.assign(notif.link);
    }
    removeNotification(notif.id);
  };

  if (notifications.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {notifications.map(notif => (
        <div 
          key={notif.id} 
          onClick={() => handleNotificationClick(notif)}
          className={`bg-white border border-slate-200 shadow-lg rounded-xl p-4 flex items-start gap-3 w-80 pointer-events-auto transform transition-all duration-300 translate-x-0 ${notif.link ? 'cursor-pointer hover:shadow-xl hover:-translate-y-0.5' : ''}`}
        >
          {notif.result === 'success' ? (
            <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
          ) : notif.result === 'error' ? (
            <AlertCircle className="w-5 h-5 text-rose-500 flex-shrink-0 mt-0.5" />
          ) : (
            <Bell className="w-5 h-5 text-indigo-500 flex-shrink-0 mt-0.5" />
          )}
          
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-slate-800">
              {notif.title}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              {notif.message}
            </p>
          </div>

          <button 
            onClick={(e) => {
              e.stopPropagation();
              removeNotification(notif.id);
            }}
            className="text-slate-400 hover:text-slate-600 transition p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
