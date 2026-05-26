import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import ChatInterface from 'src/pages/ChatInterface';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { FeaturesContext, DEFAULT_FEATURES } from 'src/features.context';
import * as usePermissionsModule from 'src/hooks/usePermissions';
import * as useChatHistoryModule from 'src/hooks/useChatHistory';
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';

jest.mock('src/hooks/usePermissions', () => ({
  usePermissionState: jest.fn(),
}));

jest.mock('src/hooks/useChatHistory', () => ({
  useChatHistory: jest.fn(),
}));

jest.mock('@ai-sdk/react', () => ({
  useChat: jest.fn(),
}));

jest.mock('ai', () => ({
  DefaultChatTransport: jest.fn().mockImplementation((options: object) => ({
    options,
  })),
}));

const mockUsePermissionState =
  usePermissionsModule.usePermissionState as jest.MockedFunction<
    typeof usePermissionsModule.usePermissionState
  >;
const mockUseChatHistory =
  useChatHistoryModule.useChatHistory as jest.MockedFunction<
    typeof useChatHistoryModule.useChatHistory
  >;
const mockUseChat = useChat as jest.MockedFunction<typeof useChat>;
const mockDefaultChatTransport = DefaultChatTransport as jest.MockedClass<
  typeof DefaultChatTransport
>;
const theme = createTheme();

function renderChat({
  accessToken = 'token-123',
  chatEnabled = true,
}: {
  accessToken?: string | null;
  chatEnabled?: boolean;
} = {}) {
  return render(
    <AuthConfigContext.Provider
      value={{ auth_required: accessToken !== null, oidc: null, loaded: true }}
    >
      <FeaturesContext.Provider
        value={{ ...DEFAULT_FEATURES, chat: chatEnabled }}
      >
        <AuthContext.Provider value={{ accessToken, isLoading: false }}>
          <ThemeProvider theme={theme}>
            <ChatInterface />
          </ThemeProvider>
        </AuthContext.Provider>
      </FeaturesContext.Provider>
    </AuthConfigContext.Provider>,
  );
}

describe('ChatInterface', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.localStorage.clear();
    mockUseChatHistory.mockReturnValue(() => Promise.resolve([]));
    mockUsePermissionState.mockReturnValue({
      hasPermission: (permission: string) => permission === 'chat:use',
      loading: false,
      currentUser: null,
    });
    mockUseChat.mockReturnValue({
      id: 'chat-id',
      messages: [],
      sendMessage: jest.fn(),
      regenerate: jest.fn(),
      stop: jest.fn(),
      resumeStream: jest.fn(),
      addToolResult: jest.fn(),
      addToolOutput: jest.fn(),
      addToolApprovalResponse: jest.fn(),
      status: 'ready',
      error: undefined,
      setMessages: jest.fn(),
      clearError: jest.fn(),
    });
  });

  afterEach(cleanup);

  it('persists a stable thread id and configures the chat stream request body', async () => {
    renderChat();
    await act(async () => {}); // flush the on-mount history fetch

    const threadId = window.localStorage.getItem('seizu:chat:thread-id');
    expect(threadId).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );

    const transportOptions = mockDefaultChatTransport.mock.calls[0][0];
    expect(transportOptions.api).toBe('/api/v1/chat/stream');
    expect(transportOptions.headers).toEqual({
      Authorization: 'Bearer token-123',
      'X-Seizu-Csrf': '1',
    });

    const prepared = transportOptions.prepareSendMessagesRequest?.({
      id: 'chat-id',
      messages: [
        {
          id: 'user-message',
          role: 'user',
          parts: [{ type: 'text', text: 'Hello graph' }],
        },
      ],
      requestMetadata: undefined,
      body: undefined,
      credentials: 'same-origin',
      headers: transportOptions.headers as HeadersInit,
      api: '/api/v1/chat/stream',
      trigger: 'submit-message',
      messageId: 'user-message',
    }) as { body: { message: string; thread_id: string } } | undefined;

    expect(prepared?.body.message).toBe('Hello graph');
    expect(prepared?.body.thread_id).toBe(threadId);
  });

  it('shows a disabled message when the chat feature is off', () => {
    const fetchHistory = jest.fn().mockResolvedValue([]);
    mockUseChatHistory.mockReturnValue(fetchHistory);

    renderChat({ chatEnabled: false });

    expect(screen.getByText('Chat is not enabled.')).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText('Ask about your security graph...'),
    ).not.toBeInTheDocument();
    expect(fetchHistory).not.toHaveBeenCalled();
  });

  it('rehydrates persisted history into the chat on mount', async () => {
    const history = [
      {
        id: 'h1',
        role: 'user' as const,
        parts: [{ type: 'text' as const, text: 'Earlier question' }],
      },
      {
        id: 'h2',
        role: 'assistant' as const,
        parts: [{ type: 'text' as const, text: 'Earlier answer' }],
      },
    ];
    const fetchHistory = jest.fn().mockResolvedValue(history);
    mockUseChatHistory.mockReturnValue(fetchHistory);
    const setMessages = jest.fn();
    mockUseChat.mockReturnValue({
      id: 'chat-id',
      messages: [],
      sendMessage: jest.fn(),
      regenerate: jest.fn(),
      stop: jest.fn(),
      resumeStream: jest.fn(),
      addToolResult: jest.fn(),
      addToolOutput: jest.fn(),
      addToolApprovalResponse: jest.fn(),
      status: 'ready',
      error: undefined,
      setMessages,
      clearError: jest.fn(),
    });

    renderChat();

    const threadId = window.localStorage.getItem('seizu:chat:thread-id');
    await waitFor(() => {
      expect(fetchHistory).toHaveBeenCalledWith(threadId);
      expect(setMessages).toHaveBeenCalledTimes(1);
    });
    // The updater fills history only when the client list is still empty.
    const updater = setMessages.mock.calls[0][0] as (m: unknown[]) => unknown[];
    expect(updater([])).toEqual(history);
    expect(updater([{ id: 'existing' }])).toEqual([{ id: 'existing' }]);
  });

  it('sends typed input through useChat', async () => {
    const sendMessage = jest.fn();
    mockUseChat.mockReturnValue({
      id: 'chat-id',
      messages: [],
      sendMessage,
      regenerate: jest.fn(),
      stop: jest.fn(),
      resumeStream: jest.fn(),
      addToolResult: jest.fn(),
      addToolOutput: jest.fn(),
      addToolApprovalResponse: jest.fn(),
      status: 'ready',
      error: undefined,
      setMessages: jest.fn(),
      clearError: jest.fn(),
    });

    renderChat();
    fireEvent.change(
      screen.getByPlaceholderText('Ask about your security graph...'),
      {
        target: { value: 'Map my graph' },
      },
    );
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(sendMessage).toHaveBeenCalledWith({ text: 'Map my graph' });
    });
  });

  it('renders streamed assistant text parts', async () => {
    mockUseChat.mockReturnValue({
      id: 'chat-id',
      messages: [
        {
          id: 'assistant-message',
          role: 'assistant',
          parts: [{ type: 'text', text: 'Streaming response' }],
        },
      ],
      sendMessage: jest.fn(),
      regenerate: jest.fn(),
      stop: jest.fn(),
      resumeStream: jest.fn(),
      addToolResult: jest.fn(),
      addToolOutput: jest.fn(),
      addToolApprovalResponse: jest.fn(),
      status: 'streaming',
      error: undefined,
      setMessages: jest.fn(),
      clearError: jest.fn(),
    });

    renderChat();
    await act(async () => {}); // flush the on-mount history fetch

    expect(screen.getByText('Assistant')).toBeInTheDocument();
    expect(screen.getByText('Streaming response')).toBeInTheDocument();
  });
});
