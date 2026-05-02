import { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Link,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import HistoryIcon from '@mui/icons-material/History';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import RestoreIcon from '@mui/icons-material/Restore';
import { useNavigate, useParams } from 'react-router-dom';
import { Helmet } from 'react-helmet';
import {
  SkillVersion,
  useSkillMutations,
  useSkillVersionsList
} from 'src/hooks/useSkillsetsApi';
import UserDisplay from 'src/components/UserDisplay';
import { usePermissions } from 'src/hooks/usePermissions';

interface RowMenuProps {
  isCurrent: boolean;
  onRestore: () => void;
}

function RowMenu({ isCurrent, onRestore }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const hasPermission = usePermissions();
  const canWrite = hasPermission('skills:write');
  const restoreDisabled = isCurrent || !canWrite;
  const restoreTooltip = isCurrent
    ? 'This is already the current version'
    : !canWrite
      ? 'You do not have permission to restore skill versions'
      : '';
  const close = () => setAnchor(null);

  return (
    <>
      <Tooltip title="More actions">
        <IconButton aria-label="More actions" size="small" onClick={(e) => setAnchor(e.currentTarget)}>
          <MoreVertIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Menu
        anchorEl={anchor}
        open={!!anchor}
        onClose={close}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { sx: { minWidth: 180 } } }}
      >
        <Tooltip title={restoreTooltip} placement="left">
          <span>
            <MenuItem onClick={() => { onRestore(); close(); }} disabled={restoreDisabled}>
              <ListItemIcon>
                <RestoreIcon fontSize="small" color={restoreDisabled ? 'disabled' : 'inherit'} />
              </ListItemIcon>
              <ListItemText>Restore</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>
      </Menu>
    </>
  );
}

function SkillVersionDetailDialog({
  version,
  onClose
}: {
  version: SkillVersion | null;
  onClose: () => void;
}) {
  if (!version) return null;

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{version.name}</DialogTitle>
      <DialogContent dividers>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Version</Typography>
            <Typography variant="body2">v{version.version}</Typography>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Status</Typography>
            <Chip label={version.enabled ? 'Enabled' : 'Disabled'} color={version.enabled ? 'success' : 'default'} size="small" />
          </Box>
          {version.description && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Description</Typography>
              <Typography variant="body2">{version.description}</Typography>
            </Box>
          )}
          {version.triggers.length > 0 && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Triggers</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {version.triggers.map((trigger) => <Chip key={trigger} label={trigger} size="small" />)}
              </Box>
            </Box>
          )}
          {version.tools_required.length > 0 && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Tools Required</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {version.tools_required.map((tool) => <Chip key={tool} label={tool} size="small" variant="outlined" />)}
              </Box>
            </Box>
          )}
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Template</Typography>
            <Box component="pre" sx={{ bgcolor: 'action.hover', p: 2, borderRadius: 1, whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0, fontFamily: 'monospace', fontSize: 13 }}>{version.template}</Box>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Parameters</Typography>
            {version.parameters.length === 0 ? (
              <Typography variant="body2" color="text.secondary">No parameters.</Typography>
            ) : (
              <Table size="small">
                <TableHead><TableRow><TableCell>Name</TableCell><TableCell>Type</TableCell><TableCell>Required</TableCell><TableCell>Default</TableCell><TableCell>Description</TableCell></TableRow></TableHead>
                <TableBody>
                  {version.parameters.map((param) => (
                    <TableRow key={param.name}>
                      <TableCell sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{param.name}</TableCell>
                      <TableCell>{param.type}</TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>{param.required ? 'Yes' : 'No'}</TableCell>
                      <TableCell sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>{param.default !== null && param.default !== undefined ? String(param.default) : '-'}</TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>{param.description || '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

function SkillHistory() {
  const { skillsetId, skillId } = useParams();
  const navigate = useNavigate();
  const { versions, loading, error } = useSkillVersionsList(skillsetId ?? null, skillId ?? null);
  const { updateSkill } = useSkillMutations(skillsetId ?? '');
  const [detailVersion, setDetailVersion] = useState<SkillVersion | null>(null);
  const sorted = [...versions].sort((a, b) => b.version - a.version);
  const latestVersion = sorted[0]?.version;
  const name = sorted[0]?.name;

  async function handleRestore(version: SkillVersion) {
    if (!skillId) return;
    await updateSkill(skillId, {
      name: version.name,
      description: version.description,
      template: version.template,
      parameters: version.parameters,
      triggers: version.triggers,
      tools_required: version.tools_required,
      enabled: version.enabled,
      comment: `Restored from version ${version.version}`
    });
    navigate(`/app/skillsets/${skillsetId}/skills`);
  }

  return (
    <Box sx={{ p: 3 }}>
      <Helmet><title>{name ? `History - ${name} | Seizu` : 'History | Seizu'}</title></Helmet>
      <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(`/app/skillsets/${skillsetId}/skills`)} sx={{ mb: 2 }}>Back to skills</Button>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
        <HistoryIcon color="action" /><Typography variant="h1">Version history{name ? ` - ${name}` : ''}</Typography>
      </Box>
      {loading && <CircularProgress />}
      {error && <Typography color="error">Failed to load history</Typography>}
      {!loading && !error && (
        <TableContainer component={Paper} variant="outlined">
          <Table>
            <TableHead><TableRow><TableCell>Version</TableCell><TableCell>Saved</TableCell><TableCell>Created By</TableCell><TableCell>Comment</TableCell><TableCell /></TableRow></TableHead>
            <TableBody>
              {sorted.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5}>
                    <Typography color="text.secondary" sx={{ py: 1 }}>
                      No versions found.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {sorted.map((v) => {
                const isCurrent = v.version === latestVersion;
                return (
                  <TableRow key={v.version} hover>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Link
                          href={`#skill-version-${v.version}`}
                          underline="hover"
                          color="inherit"
                          fontWeight={isCurrent ? 'bold' : 'medium'}
                          onClick={(event) => {
                            event.preventDefault();
                            setDetailVersion(v);
                          }}
                        >
                          v{v.version}
                        </Link>
                        {isCurrent && (
                          <Typography component="span" variant="caption" color="primary">
                            current
                          </Typography>
                        )}
                      </Box>
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{new Date(v.created_at).toLocaleString()}</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}><UserDisplay userId={v.created_by} /></TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{v.comment || '-'}</TableCell>
                    <TableCell align="right" sx={{ width: 48, pr: 1 }}>
                      <RowMenu
                        isCurrent={isCurrent}
                        onRestore={() => handleRestore(v)}
                      />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      <SkillVersionDetailDialog
        version={detailVersion}
        onClose={() => setDetailVersion(null)}
      />
    </Box>
  );
}

export default SkillHistory;
