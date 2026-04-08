import pytest
from app.worker import generate_chat_title_text, update_chat_title

def test_generate_chat_title_text(mocker):
    class MockResponse:
        content = "My Test Title"
    
    class MockLLM:
        def invoke(self, messages):
            return MockResponse()

    mocker.patch("app.llm.get_llm", return_value=MockLLM())
    
    title = generate_chat_title_text("Hello, this is a test message.")
    assert title == "My Test Title"

def test_update_chat_title_no_commit_if_not_owns_session(mocker):
    # Mock db
    mock_db = mocker.MagicMock()
    mock_chat = mocker.MagicMock()
    mock_chat.title = "New Chat"
    
    mock_query = mocker.MagicMock()
    mock_filter = mocker.MagicMock()
    mock_filter.first.return_value = mock_chat
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query

    mocker.patch("app.worker.generate_chat_title_text", return_value="My Test Title")
    mocker.patch("app.worker.redis_client.publish")

    update_chat_title(1, "Hello", db=mock_db, publish=True)
    
    assert mock_chat.title == "My Test Title"
    mock_db.commit.assert_not_called() # Should NOT commit if db is provided

def test_update_chat_title_commits_if_owns_session(mocker):
    mock_session = mocker.MagicMock()
    mock_chat = mocker.MagicMock()
    mock_chat.title = "New Chat"
    
    mock_query = mocker.MagicMock()
    mock_filter = mocker.MagicMock()
    mock_filter.first.return_value = mock_chat
    mock_query.filter.return_value = mock_filter
    mock_session.query.return_value = mock_query

    mocker.patch("app.worker.SessionLocal", return_value=mock_session)
    mocker.patch("app.worker.generate_chat_title_text", return_value="My Test Title")
    mocker.patch("app.worker.redis_client.publish")

    update_chat_title(1, "Hello", db=None, publish=True)
    
    assert mock_chat.title == "My Test Title"
    mock_session.commit.assert_called_once() # Should commit if it creates its own session
