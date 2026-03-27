import {
  Box,
  Chip,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { ToolItem, ToolVersion, ToolParamDef } from 'src/hooks/useToolsetsApi';

export type ToolViewData = Pick<
  ToolItem | ToolVersion,
  'name' | 'description' | 'cypher' | 'parameters' | 'enabled'
> & { version?: number };

interface Props {
  open: boolean;
  onClose: () => void;
  data: ToolViewData | null;
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

function ParamTypeChip({ type }: { type: ToolParamDef['type'] }) {
  return (
    <Chip label={type} size="small" variant="outlined" sx={{ fontFamily: 'monospace', fontSize: 11 }} />
  );
}

export default function ToolDetailDialog({ open, onClose, data }: Props) {
  if (!data) return null;

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

          {data.description && (
            <Section title="Description">
              <Typography variant="body2">{data.description}</Typography>
            </Section>
          )}

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

          {data.parameters.length > 0 && (
            <Section title="Parameters">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Required</TableCell>
                    <TableCell>Default</TableCell>
                    <TableCell>Description</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.parameters.map((p, i) => (
                    <TableRow key={i}>
                      <TableCell sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{p.name}</TableCell>
                      <TableCell><ParamTypeChip type={p.type} /></TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {p.required ? 'Yes' : 'No'}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
                        {p.default !== null && p.default !== undefined ? String(p.default) : '—'}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>{p.description || '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Section>
          )}
        </Box>
      </DialogContent>
    </Dialog>
  );
}
