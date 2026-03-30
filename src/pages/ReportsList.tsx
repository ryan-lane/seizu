import { useState } from 'react';
import { Link as RouterLink, useNavigate, useSearchParams } from 'react-router-dom';
import { Helmet } from 'react-helmet';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
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
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import Add from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import HistoryIcon from '@mui/icons-material/History';
import DashboardIcon from '@mui/icons-material/Dashboard';
import DashboardOutlinedIcon from '@mui/icons-material/DashboardOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import Error from '@mui/icons-material/Error';

import {
  ReportListItem,
  useDashboardReportId,
  useReportsList,
  useReportsMutations
} from 'src/hooks/useReportsApi';
import { usePermissions } from 'src/hooks/usePermissions';

// ---------------------------------------------------------------------------
// Per-row overflow menu
// ---------------------------------------------------------------------------

interface RowMenuProps {
  report: ReportListItem;
  isDashboard: boolean;
  onSetDashboard: () => void;
  onEdit: () => void;
  onHistory: () => void;
  onDelete: () => void;
}

function RowMenu({ report: _report, isDashboard, onSetDashboard, onEdit, onHistory, onDelete }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const hasPermission = usePermissions();

  const canWrite = hasPermission('reports:write');
  const canDelete = hasPermission('reports:delete');
  const canSetDashboard = hasPermission('reports:set_dashboard');

  const close = () => setAnchor(null);

  return (
    <>
      <Tooltip title="More actions">
        <IconButton size="small" onClick={(e) => setAnchor(e.currentTarget)}>
          <MoreVertIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      <Menu
        anchorEl={anchor}
        open={!!anchor}
        onClose={close}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { sx: { minWidth: 200 } } }}
      >
        <Tooltip title={!canWrite ? 'You do not have permission to edit reports' : ''} placement="left">
          <span>
            <MenuItem
              onClick={() => { onEdit(); close(); }}
              disabled={!canWrite}
            >
              <ListItemIcon><EditIcon fontSize="small" /></ListItemIcon>
              <ListItemText>Edit</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>

        <MenuItem
          onClick={() => { onHistory(); close(); }}
        >
          <ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon>
          <ListItemText>View history</ListItemText>
        </MenuItem>

        <Tooltip title={!canSetDashboard ? 'You do not have permission to set the dashboard' : ''} placement="left">
          <span>
            <MenuItem
              onClick={() => { onSetDashboard(); close(); }}
              disabled={isDashboard || !canSetDashboard}
            >
              <ListItemIcon>
                {isDashboard ? <DashboardIcon fontSize="small" color="primary" /> : <DashboardOutlinedIcon fontSize="small" />}
              </ListItemIcon>
              <ListItemText>{isDashboard ? 'Current dashboard' : 'Set as dashboard'}</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>

        <Divider />

        <Tooltip title={!canDelete ? 'You do not have permission to delete reports' : ''} placement="left">
          <span>
            <MenuItem
              onClick={() => { onDelete(); close(); }}
              disabled={!canDelete}
              sx={{ color: canDelete ? 'error.main' : undefined }}
            >
              <ListItemIcon><DeleteIcon fontSize="small" color={canDelete ? 'error' : 'disabled'} /></ListItemIcon>
              <ListItemText>Delete</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>
      </Menu>
    </>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function ReportsList() {
  const { reports, loading, error, refresh } = useReportsList();
  const { dashboardReportId, refresh: refreshDashboard } = useDashboardReportId();
  const { createReport, saveReportVersion, setDashboardReport, deleteReport } =
    useReportsMutations();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const hasPermission = usePermissions();

  const [createOpen, setCreateOpen] = useState(() => searchParams.get('new') === '1');
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<ReportListItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const item = await createReport(newName.trim());
      await saveReportVersion(
        item.report_id,
        { name: newName.trim(), rows: [], schema_version: 1 },
        'Initial version'
      );
      setCreateOpen(false);
      setNewName('');
      navigate(`/app/reports/${item.report_id}?edit=true`);
    } catch (err) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setCreateError((err as any)?.message ?? 'Failed to create report');
    } finally {
      setCreating(false);
    }
  };

  const handleSetDashboard = async (reportId: string) => {
    try {
      await setDashboardReport(reportId);
      refreshDashboard();
    } catch {
      // ignore – user can retry
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteReport(deleteTarget.report_id);
      setDeleteTarget(null);
      refresh();
    } catch {
      // dialog stays open so user can retry
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <Helmet>
        <title>Reports | Seizu</title>
      </Helmet>
      <Box sx={{ p: 3 }}>
        <Box
          sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}
        >
          <Typography variant="h1">Reports</Typography>
          {hasPermission('reports:write') && (
            <Button variant="contained" startIcon={<Add />} onClick={() => setCreateOpen(true)}>
              New report
            </Button>
          )}
        </Box>

        {loading && <CircularProgress />}

        {error && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Error />
            <Typography>Failed to load reports</Typography>
          </Box>
        )}

        {!loading && !error && (
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Version</TableCell>
                  <TableCell>Last updated</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {reports.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4}>
                      <Typography color="text.secondary" sx={{ py: 1 }}>
                        No reports yet. Create one above.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
                {reports.map((report) => {
                  const isDashboard = report.report_id === dashboardReportId;
                  return (
                    <TableRow key={report.report_id} hover>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Link
                            component={RouterLink}
                            to={`/app/reports/${report.report_id}`}
                            underline="hover"
                            color="inherit"
                            fontWeight="medium"
                          >
                            {report.name}
                          </Link>
                          {isDashboard && (
                            <Tooltip title="Currently set as the dashboard">
                              <Chip
                                icon={<DashboardIcon sx={{ fontSize: '0.85rem !important' }} />}
                                label="Dashboard"
                                size="small"
                                color="primary"
                                variant="outlined"
                                sx={{ height: 20, fontSize: '0.7rem' }}
                              />
                            </Tooltip>
                          )}
                        </Box>
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        v{report.current_version}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {new Date(report.updated_at).toLocaleString()}
                      </TableCell>
                      <TableCell align="right" sx={{ width: 48, pr: 1 }}>
                        <RowMenu
                          report={report}
                          isDashboard={isDashboard}
                          onSetDashboard={() => handleSetDashboard(report.report_id)}
                          onEdit={() => navigate(`/app/reports/${report.report_id}?edit=true`)}
                          onHistory={() => navigate(`/app/reports/${report.report_id}/history`)}
                          onDelete={() => setDeleteTarget(report)}
                        />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      {/* Create dialog */}
      <Dialog
        open={createOpen}
        onClose={() => {
          setCreateOpen(false);
          setSearchParams({}, { replace: true });
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>New report</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            label="Report name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            error={!!createError}
            helperText={createError ?? ''}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setCreateOpen(false);
              setSearchParams({}, { replace: true });
            }}
            disabled={creating}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={creating || !newName.trim()}
          >
            {creating ? <CircularProgress size={20} /> : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete report?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Permanently delete <strong>{deleteTarget?.name}</strong> and all its versions? This
            cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)} disabled={deleting}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleDeleteConfirm}
            disabled={deleting}
          >
            {deleting ? <CircularProgress size={20} /> : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export default ReportsList;
