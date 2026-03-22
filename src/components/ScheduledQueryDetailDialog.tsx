import {
  Box,
  Chip,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Tooltip,
  Typography
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import {
  ScheduledQueryParam,
  ScheduledQueryWatchScan,
  ScheduledQueryAction
} from 'src/hooks/useScheduledQueriesApi';

export interface ScheduledQueryViewData {
  name: string;
  version?: number;
  cypher: string;
  params: ScheduledQueryParam[];
  frequency: number | null;
  watch_scans: ScheduledQueryWatchScan[];
  enabled: boolean;
  actions: ScheduledQueryAction[];
}

interface Props {
  open: boolean;
  onClose: () => void;
  data: ScheduledQueryViewData | null;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
        {title}
      </Typography>
      {children}
    </Box>
  );
}

export default function ScheduledQueryDetailDialog({ open, onClose, data }: Props) {
  if (!data) return null;

  const triggerLabel =
    data.watch_scans.length > 0
      ? `Watch scans (${data.watch_scans.length})`
      : data.frequency != null
        ? `Every ${data.frequency} min`
        : 'Not configured';

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle
        sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pr: 1 }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {data.name}
          {data.version !== undefined && (
            <Typography component="span" variant="body2" color="text.secondary">
              v{data.version}
            </Typography>
          )}
        </Box>
        <Tooltip title="Close">
          <IconButton size="small" onClick={onClose}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </DialogTitle>

      <Divider />

      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          <Section title="Status">
            <Chip
              label={data.enabled ? 'Enabled' : 'Disabled'}
              color={data.enabled ? 'success' : 'default'}
              size="small"
            />
          </Section>

          <Section title="Trigger">
            <Typography variant="body2">{triggerLabel}</Typography>
            {data.watch_scans.length > 0 && (
              <Box sx={{ mt: 0.5 }}>
                {data.watch_scans.map((ws, i) => (
                  <Typography key={i} variant="caption" color="text.secondary" display="block">
                    grouptype: {ws.grouptype ?? '*'} &nbsp;·&nbsp; syncedtype: {ws.syncedtype ?? '*'} &nbsp;·&nbsp; groupid: {ws.groupid ?? '*'}
                  </Typography>
                ))}
              </Box>
            )}
          </Section>

          <Section title="Cypher">
            <Box
              component="pre"
              sx={{
                m: 0,
                p: 1.5,
                borderRadius: 1,
                bgcolor: 'action.hover',
                fontSize: 12,
                fontFamily: 'monospace',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                overflowX: 'auto'
              }}
            >
              {data.cypher}
            </Box>
          </Section>

          {data.params.length > 0 && (
            <Section title="Parameters">
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                {data.params.map((p, i) => (
                  <Box key={i} sx={{ display: 'flex', gap: 1 }}>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600, minWidth: 120 }}>
                      {p.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                      {Array.isArray(p.value) ? (p.value as unknown[]).join(', ') : String(p.value ?? '')}
                      {Array.isArray(p.value) && (
                        <Typography component="span" variant="caption" color="text.disabled" sx={{ ml: 0.5 }}>
                          (list)
                        </Typography>
                      )}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Section>
          )}

          {data.actions.length > 0 && (
            <Section title="Actions">
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {data.actions.map((a, i) => (
                  <Box
                    key={i}
                    sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1.5 }}
                  >
                    <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
                      {a.action_type}
                    </Typography>
                    {Object.keys(a.action_config).length > 0 && (
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
                        {Object.entries(a.action_config).map(([k, v]) => (
                          <Box key={k} sx={{ display: 'flex', gap: 1 }}>
                            <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace', minWidth: 140 }}>
                              {k}
                            </Typography>
                            <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                              {Array.isArray(v) ? (v as unknown[]).join(', ') : String(v ?? '')}
                            </Typography>
                          </Box>
                        ))}
                      </Box>
                    )}
                  </Box>
                ))}
              </Box>
            </Section>
          )}
        </Box>
      </DialogContent>
    </Dialog>
  );
}
