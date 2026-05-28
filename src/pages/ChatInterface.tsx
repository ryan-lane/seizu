import {
  ChangeEvent,
  FormEvent,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport, type UIMessage } from 'ai';
import {
  Alert,
  Box,
  CircularProgress,
  IconButton,
  Paper,
  Tooltip,
  Typography,
} from '@mui/material';
import Send from '@mui/icons-material/Send';
import Stop from '@mui/icons-material/Stop';
import SmartToy from '@mui/icons-material/SmartToy';
import Person from '@mui/icons-material/Person';
import Check from '@mui/icons-material/Check';
import ContentCopy from '@mui/icons-material/ContentCopy';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { usePermissionState } from 'src/hooks/usePermissions';
import { useChatHistory } from 'src/hooks/useChatHistory';
import { useFeature } from 'src/features.context';
import { MarkdocRenderer } from 'src/components/markdoc/renderer';
import { pageContentSx } from 'src/theme/layout';

const CHAT_THREAD_STORAGE_KEY = 'seizu:chat:thread-id';
const CHAT_MESSAGE_THROTTLE_MS = 50;

// Persist the thread id so a reload resumes the same server-side conversation;
// the client message list is rehydrated from the server on mount (see below).
function getInitialThreadId(): string {
  if (typeof window === 'undefined') return crypto.randomUUID();
  const existing = window.localStorage.getItem(CHAT_THREAD_STORAGE_KEY);
  if (existing) return existing;
  const next = crypto.randomUUID();
  window.localStorage.setItem(CHAT_THREAD_STORAGE_KEY, next);
  return next;
}

function messageText(message: UIMessage): string {
  return message.parts
    .filter((part) => part.type === 'text')
    .map((part) => part.text)
    .join('');
}

function latestUserText(messages: UIMessage[]): string {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role === 'user') return messageText(message);
  }
  return '';
}

export default function ChatInterface() {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const { hasPermission, loading: permissionsLoading } = usePermissionState();
  const chatEnabled = useFeature('chat');
  const fetchHistory = useChatHistory();
  const [input, setInput] = useState('');
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [threadId] = useState(getInitialThreadId);
  const [historyLoading, setHistoryLoading] = useState(true);
  const hydratedRef = useRef(false);
  const messagesRef = useRef<UIMessage[]>([]);
  const setMessagesRef = useRef<
    (messages: UIMessage[] | ((messages: UIMessage[]) => UIMessage[])) => void
  >(() => {});
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const transport = useMemo(
    () =>
      new DefaultChatTransport<UIMessage>({
        api: '/api/v1/chat/stream',
        headers: accessToken
          ? { Authorization: `Bearer ${accessToken}`, 'X-Seizu-Csrf': '1' }
          : { 'X-Seizu-Csrf': '1' },
        prepareSendMessagesRequest: ({ messages, headers }) => ({
          headers,
          body: {
            message: latestUserText(messages),
            thread_id: threadId,
          },
        }),
      }),
    [accessToken, threadId],
  );

  const { messages, sendMessage, setMessages, status, stop, error } =
    useChat<UIMessage>({
      id: threadId,
      experimental_throttle: CHAT_MESSAGE_THROTTLE_MS,
      transport,
    });

  messagesRef.current = messages;
  setMessagesRef.current = setMessages;

  const busy = status === 'submitted' || status === 'streaming';
  const showWorkingIndicator = busy;
  const canUseChat = hasPermission('chat:use');
  const disabled = permissionsLoading || !canUseChat;
  const waitingForToken = auth_required && !accessToken;

  // Rehydrate the conversation from the server once, after auth/permissions
  // resolve. Only fill in if the client list is still empty so we never clobber
  // a message the user sent before history arrived.
  useEffect(() => {
    if (!chatEnabled || permissionsLoading || waitingForToken || !canUseChat)
      return;
    if (hydratedRef.current) return;
    hydratedRef.current = true;
    let cancelled = false;
    void fetchHistory(threadId).then((history) => {
      if (cancelled) return;
      if (history.length > 0 && messagesRef.current.length === 0) {
        setMessagesRef.current(history);
      }
      setHistoryLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [
    chatEnabled,
    threadId,
    fetchHistory,
    permissionsLoading,
    waitingForToken,
    canUseChat,
  ]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ block: 'end' });
  }, [messages]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || busy || disabled || waitingForToken) return;
    setInput('');
    void sendMessage({ text: trimmed });
  };

  const handleInputChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(event.target.value);
  };

  const handleCopyAssistantResponse = async (message: UIMessage) => {
    const text = messageText(message);
    if (!text || !navigator.clipboard) return;
    await navigator.clipboard.writeText(text);
    setCopiedMessageId(message.id);
    window.setTimeout(() => {
      setCopiedMessageId((current) =>
        current === message.id ? null : current,
      );
    }, 1800);
  };

  if (!chatEnabled) {
    return (
      <Box sx={pageContentSx}>
        <Typography>Chat is not enabled.</Typography>
      </Box>
    );
  }

  if (permissionsLoading || waitingForToken) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!canUseChat) {
    return (
      <Box sx={pageContentSx}>
        <Typography>You do not have access to chat.</Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        ...pageContentSx,
        boxSizing: 'border-box',
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        height: 'calc(100vh - 64px)',
        overflow: 'hidden',
      }}
    >
      <Box>
        <Typography variant="h1">Chat</Typography>
      </Box>

      <Paper
        elevation={0}
        sx={{
          border: 1,
          borderColor: 'divider',
          display: 'flex',
          flex: 1,
          flexDirection: 'column',
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            px: { xs: 2, md: 3 },
            py: 2,
          }}
        >
          {historyLoading && messages.length === 0 ? (
            <Box
              sx={{
                alignItems: 'center',
                display: 'flex',
                height: '100%',
                justifyContent: 'center',
              }}
            >
              <CircularProgress />
            </Box>
          ) : messages.length === 0 ? (
            <Box
              sx={{
                alignItems: 'center',
                color: 'text.secondary',
                display: 'flex',
                height: '100%',
                justifyContent: 'center',
                textAlign: 'center',
              }}
            >
              <Typography variant="body2">
                Start a conversation with the graph assistant.
              </Typography>
            </Box>
          ) : (
            <>
              {messages.map((message) => {
                const text = messageText(message);
                const copied = copiedMessageId === message.id;
                return (
                  <Box
                    key={message.id}
                    sx={{
                      alignItems:
                        message.role === 'user' ? 'flex-end' : 'flex-start',
                      display: 'flex',
                      flexDirection: 'column',
                      mb: 1.5,
                    }}
                  >
                    <Box
                      sx={{
                        alignItems: 'center',
                        color: 'text.secondary',
                        display: 'flex',
                        gap: 0.75,
                        mb: 0.5,
                      }}
                    >
                      {message.role === 'user' ? (
                        <Person fontSize="small" />
                      ) : (
                        <SmartToy fontSize="small" />
                      )}
                      <Typography variant="caption">
                        {message.role === 'user' ? 'You' : 'Assistant'}
                      </Typography>
                    </Box>
                    <Box
                      sx={{
                        bgcolor:
                          message.role === 'user'
                            ? 'primary.main'
                            : 'action.hover',
                        borderRadius: 2,
                        color:
                          message.role === 'user'
                            ? 'primary.contrastText'
                            : 'text.primary',
                        maxWidth: { xs: '92%', md: '74%' },
                        px: 1.5,
                        py: 1,
                        whiteSpace:
                          message.role === 'user' ? 'pre-wrap' : 'normal',
                        wordBreak: 'break-word',
                      }}
                    >
                      {message.role === 'user' ? (
                        <Typography variant="body2">
                          {text || (busy ? '...' : '')}
                        </Typography>
                      ) : (
                        <Box
                          sx={(theme) => ({
                            '& > :first-child': { mt: 0 },
                            '& > :last-child': { mb: 0 },
                            '& p': { mb: 1, mt: 0 },
                            '& ul, & ol': { my: 1, pl: 3 },
                            '& li': { mb: 0.5 },
                            '& h2, & h3, & h4, & h5, & h6': {
                              fontSize: theme.typography.subtitle2.fontSize,
                              lineHeight: 1.4,
                              mb: 1,
                              mt: 1.25,
                            },
                            '& hr': {
                              border: 0,
                              borderTop: 1,
                              borderColor: 'divider',
                              my: 2,
                            },
                            '& pre': {
                              bgcolor: 'background.paper',
                              border: 1,
                              borderColor: 'divider',
                              borderRadius: 1,
                              fontFamily: '"JetBrains Mono", monospace',
                              fontSize: theme.typography.body2.fontSize,
                              lineHeight: 1.6,
                              my: 1.25,
                              overflowX: 'auto',
                              p: 1,
                              whiteSpace: 'pre',
                            },
                            '& code': {
                              bgcolor: 'background.paper',
                              borderRadius: 0.5,
                              fontFamily: '"JetBrains Mono", monospace',
                              fontSize: '0.92em',
                              px: 0.5,
                            },
                            '& pre code': {
                              bgcolor: 'transparent',
                              borderRadius: 0,
                              display: 'block',
                              fontSize: 'inherit',
                              lineHeight: 'inherit',
                              p: 0,
                              whiteSpace: 'inherit',
                            },
                            '& img': {
                              height: 'auto',
                              maxWidth: '100%',
                            },
                          })}
                        >
                          <MarkdocRenderer
                            source={text || (busy ? '...' : '')}
                            untrustedUrls
                          />
                          <Box
                            aria-label="Assistant response actions"
                            sx={{
                              alignItems: 'center',
                              display: 'flex',
                              gap: 0.5,
                              justifyContent: 'flex-start',
                              mt: 1,
                            }}
                          >
                            <Tooltip
                              title={copied ? 'Copied' : 'Copy response'}
                            >
                              <span>
                                <IconButton
                                  aria-label="Copy assistant response"
                                  disabled={!text}
                                  onClick={() => {
                                    void handleCopyAssistantResponse(message);
                                  }}
                                  size="small"
                                  sx={{ color: 'text.secondary', p: 0.25 }}
                                >
                                  {copied ? (
                                    <Check sx={{ fontSize: 16 }} />
                                  ) : (
                                    <ContentCopy sx={{ fontSize: 16 }} />
                                  )}
                                </IconButton>
                              </span>
                            </Tooltip>
                          </Box>
                        </Box>
                      )}
                    </Box>
                  </Box>
                );
              })}
              {showWorkingIndicator ? (
                <Box
                  sx={{
                    alignItems: 'center',
                    color: 'text.secondary',
                    display: 'flex',
                    gap: 1,
                    mb: 1.5,
                  }}
                >
                  <CircularProgress size={14} />
                  <Typography variant="body2">
                    Assistant is working...
                  </Typography>
                </Box>
              ) : null}
            </>
          )}
          <div ref={scrollRef} />
        </Box>

        {error ? (
          <Alert severity="error" sx={{ borderRadius: 0 }}>
            {error.message}
          </Alert>
        ) : null}

        <Box
          component="form"
          onSubmit={handleSubmit}
          sx={{
            alignItems: 'flex-end',
            borderTop: 1,
            borderColor: 'divider',
            display: 'flex',
            gap: 1,
            p: 2,
          }}
        >
          <Box
            component="textarea"
            value={input}
            onChange={handleInputChange}
            placeholder="Ask about your security graph..."
            disabled={busy}
            sx={(theme) => ({
              bgcolor: 'background.paper',
              border: 1,
              borderColor: 'divider',
              borderRadius: 1,
              boxSizing: 'border-box',
              color: 'text.primary',
              flex: 1,
              font: 'inherit',
              lineHeight: 1.5,
              maxHeight: 120,
              minHeight: 44,
              outline: 0,
              overflowY: 'auto',
              px: 1.5,
              py: 1.1,
              resize: 'none',
              width: '100%',
              '&::placeholder': {
                color: 'text.secondary',
                opacity: 1,
              },
              '&:focus': {
                borderColor: 'primary.main',
                boxShadow: `0 0 0 1px ${theme.palette.primary.main}`,
              },
              '&:disabled': {
                bgcolor: 'action.disabledBackground',
                color: 'text.disabled',
              },
            })}
          />
          {busy ? (
            <Tooltip title="Stop">
              <IconButton color="primary" onClick={stop} aria-label="Stop">
                <Stop />
              </IconButton>
            </Tooltip>
          ) : (
            <Tooltip title="Send">
              <span>
                <IconButton
                  type="submit"
                  color="primary"
                  disabled={
                    !input.trim() || busy || disabled || waitingForToken
                  }
                  aria-label="Send"
                >
                  <Send />
                </IconButton>
              </span>
            </Tooltip>
          )}
        </Box>
      </Paper>
    </Box>
  );
}
