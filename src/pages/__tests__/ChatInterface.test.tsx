import {
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
import * as usePermissionsModule from 'src/hooks/usePermissions';
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';

jest.mock('src/hooks/usePermissions', () => ({
  usePermissionState: jest.fn(),
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
const mockUseChat = useChat as jest.MockedFunction<typeof useChat>;
const mockDefaultChatTransport = DefaultChatTransport as jest.MockedClass<
  typeof DefaultChatTransport
>;
const theme = createTheme();

function renderChat({
  accessToken = 'token-123',
}: {
  accessToken?: string | null;
} = {}) {
  return render(
    <AuthConfigContext.Provider
      value={{ auth_required: accessToken !== null, oidc: null, loaded: true }}
    >
      <AuthContext.Provider value={{ accessToken, isLoading: false }}>
        <ThemeProvider theme={theme}>
          <ChatInterface />
        </ThemeProvider>
      </AuthContext.Provider>
    </AuthConfigContext.Provider>,
  );
}

describe('ChatInterface', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.localStorage.clear();
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

  it('stores a stable thread id and configures the chat stream request body', () => {
    renderChat();

    const threadId = window.localStorage.getItem('seizu:chat:thread-id');
    expect(threadId).toBeTruthy();
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
    }) as { body: object } | undefined;

    expect(prepared?.body).toEqual({
      message: 'Hello graph',
      thread_id: threadId,
    });
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

  it('renders streamed assistant text parts', () => {
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

    expect(screen.getByText('Assistant')).toBeInTheDocument();
    expect(screen.getByText('Streaming response')).toBeInTheDocument();
  });
});
