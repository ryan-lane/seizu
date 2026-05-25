import {
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
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import Send from '@mui/icons-material/Send';
import Stop from '@mui/icons-material/Stop';
import SmartToy from '@mui/icons-material/SmartToy';
import Person from '@mui/icons-material/Person';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { usePermissionState } from 'src/hooks/usePermissions';
import { pageContentSx } from 'src/theme/layout';

const CHAT_THREAD_STORAGE_KEY = 'seizu:chat:thread-id';

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
  const [input, setInput] = useState('');
  const [threadId] = useState(getInitialThreadId);
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

  const { messages, sendMessage, status, stop, error } = useChat<UIMessage>({
    id: threadId,
    transport,
  });

  const busy = status === 'submitted' || status === 'streaming';
  const disabled = permissionsLoading || !hasPermission('chat:use');
  const waitingForToken = auth_required && !accessToken;

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

  if (permissionsLoading || waitingForToken) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!hasPermission('chat:use')) {
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
          {messages.length === 0 ? (
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
            messages.map((message) => (
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
                      message.role === 'user' ? 'primary.main' : 'action.hover',
                    borderRadius: 2,
                    color:
                      message.role === 'user'
                        ? 'primary.contrastText'
                        : 'text.primary',
                    maxWidth: { xs: '92%', md: '74%' },
                    px: 1.5,
                    py: 1,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  <Typography variant="body2">
                    {messageText(message) || (busy ? '...' : '')}
                  </Typography>
                </Box>
              </Box>
            ))
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
          <TextField
            fullWidth
            multiline
            maxRows={5}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask about your security graph..."
            disabled={busy}
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
                  disabled={!input.trim()}
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
