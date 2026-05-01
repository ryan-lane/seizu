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
  SkillsetVersion,
  useSkillsetMutations,
  useSkillsetVersionsList
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
  const canWrite = hasPermission('skillsets:write');
  const restoreDisabled = isCurrent || !canWrite;
  const restoreTooltip = isCurrent
    ? 'This is already the current version'
    : !canWrite
      ? 'You do not have permission to restore skillset versions'
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

function SkillsetVersionDetailDialog({
  version,
  onClose
}: {
  version: SkillsetVersion | null;
  onClose: () => void;
}) {
  if (!version) return null;

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
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
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

function SkillsetHistory() {
  const { skillsetId } = useParams();
  const navigate = useNavigate();
  const { versions, loading, error } = useSkillsetVersionsList(skillsetId ?? null);
  const { updateSkillset } = useSkillsetMutations();
  const [detailVersion, setDetailVersion] = useState<SkillsetVersion | null>(null);
  const sorted = [...versions].sort((a, b) => b.version - a.version);
  const latestVersion = sorted[0]?.version;
  const name = sorted[0]?.name;

  async function handleRestore(version: SkillsetVersion) {
    if (!skillsetId) return;
    await updateSkillset(skillsetId, {
      name: version.name,
      description: version.description,
      enabled: version.enabled,
      comment: `Restored from version ${version.version}`
    });
    navigate('/app/skillsets');
  }

  return (
    <Box sx={{ p: 3 }}>
      <Helmet><title>{name ? `History - ${name} | Seizu` : 'History | Seizu'}</title></Helmet>
      <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/app/skillsets')} sx={{ mb: 2 }}>Back to skillsets</Button>
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
                          href={`#skillset-version-${v.version}`}
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
      <SkillsetVersionDetailDialog
        version={detailVersion}
        onClose={() => setDetailVersion(null)}
      />
    </Box>
  );
}

export default SkillsetHistory;
