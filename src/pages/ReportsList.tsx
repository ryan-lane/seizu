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
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import Add from '@mui/icons-material/Add';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import HistoryIcon from '@mui/icons-material/History';
import DashboardIcon from '@mui/icons-material/Dashboard';
import DashboardOutlinedIcon from '@mui/icons-material/DashboardOutlined';
import LockIcon from '@mui/icons-material/Lock';
import PushPinIcon from '@mui/icons-material/PushPin';
import PushPinOutlinedIcon from '@mui/icons-material/PushPinOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import PublicIcon from '@mui/icons-material/Public';
import Error from '@mui/icons-material/Error';

import {
  ReportListItem,
  useDashboardReportId,
  useReportsList,
  useReportsMutations
} from 'src/hooks/useReportsApi';
import { usePermissionState } from 'src/hooks/usePermissions';
import ListTable, {
  ListTableColumn,
  listTableActionColumnSx,
  listTablePrimaryCellSx,
  listTableSecondaryCellSx
} from 'src/components/ListTable';
import UserDisplay from 'src/components/UserDisplay';
import type { BackState } from 'src/navigation';
import { pageContentSx } from 'src/theme/layout';

// ---------------------------------------------------------------------------
// Per-row overflow menu
// ---------------------------------------------------------------------------

interface RowMenuProps {
  report: ReportListItem;
  isDashboard: boolean;
  onSetDashboard: () => void;
  onPin: () => void;
  onEdit: () => void;
  onHistory: () => void;
  onClone: () => void;
  onToggleAccess: () => void;
  onDelete: () => void;
  isOwner: boolean;
  hasPermission: (permission: string) => boolean;
}

function RowMenu({
  report,
  isDashboard,
  onSetDashboard,
  onPin,
  onEdit,
  onHistory,
  onClone,
  onToggleAccess,
  onDelete,
  isOwner,
  hasPermission
}: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);

  const canWrite = hasPermission('reports:write');
  const canDelete = hasPermission('reports:delete');
  const canSetDashboard = hasPermission('reports:set_dashboard');
  const canUpdateAccess = canWrite && isOwner;

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

        <Tooltip title={!canWrite ? 'You do not have permission to clone reports' : ''} placement="left">
          <span>
            <MenuItem
              onClick={() => { onClone(); close(); }}
              disabled={!canWrite}
            >
              <ListItemIcon><ContentCopyIcon fontSize="small" /></ListItemIcon>
              <ListItemText>Clone</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>

        <Tooltip title={!canSetDashboard ? 'You do not have permission to set the dashboard' : ''} placement="left">
          <span>
            <MenuItem
              onClick={() => { onSetDashboard(); close(); }}
              disabled={isDashboard || !canSetDashboard || report.access.scope !== 'public'}
            >
              <ListItemIcon>
                {isDashboard ? <DashboardIcon fontSize="small" color="primary" /> : <DashboardOutlinedIcon fontSize="small" />}
              </ListItemIcon>
              <ListItemText>{isDashboard ? 'Current dashboard' : 'Set as dashboard'}</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>

        <Tooltip
          title={
            !canUpdateAccess
              ? 'Only the report owner can publish or unpublish'
              : ''
          }
          placement="left"
        >
          <span>
            <MenuItem
              onClick={() => { onToggleAccess(); close(); }}
              disabled={!canUpdateAccess}
            >
              <ListItemIcon>
                {report.access.scope === 'public'
                  ? <LockIcon fontSize="small" />
                  : <PublicIcon fontSize="small" />}
              </ListItemIcon>
              <ListItemText>{report.access.scope === 'public' ? 'Unpublish' : 'Publish'}</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>

        <Tooltip title={!canWrite ? 'You do not have permission to pin reports' : ''} placement="left">
          <span>
            <MenuItem
              onClick={() => { onPin(); close(); }}
              disabled={!canWrite}
            >
              <ListItemIcon>
                {report.pinned ? <PushPinIcon fontSize="small" color="primary" /> : <PushPinOutlinedIcon fontSize="small" />}
              </ListItemIcon>
              <ListItemText>{report.pinned ? 'Unpin from sidebar' : 'Pin to sidebar'}</ListItemText>
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
  const { createReport, cloneReport, saveReportVersion, setDashboardReport, pinReport, updateReportVisibility, deleteReport } =
    useReportsMutations();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { hasPermission, loading: permissionsLoading, currentUser } = usePermissionState();

  const [createOpen, setCreateOpen] = useState(() => searchParams.get('new') === '1');
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [cloneTarget, setCloneTarget] = useState<ReportListItem | null>(null);
  const [cloneName, setCloneName] = useState('');
  const [cloning, setCloning] = useState(false);
  const [cloneError, setCloneError] = useState<string | null>(null);

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

  const handlePin = async (reportId: string, pinned: boolean) => {
    try {
      await pinReport(reportId, pinned);
      refresh();
    } catch {
      // ignore – user can retry
    }
  };

  const handleToggleAccess = async (report: ReportListItem) => {
    try {
      await updateReportVisibility(report.report_id, report.access.scope === 'public' ? 'private' : 'public');
      refresh();
      refreshDashboard();
    } catch {
      // ignore – user can retry
    }
  };

  const handleCloneOpen = (report: ReportListItem) => {
    setCloneTarget(report);
    setCloneName(`Copy of ${report.name}`);
    setCloneError(null);
  };

  const handleCloneConfirm = async () => {
    if (!cloneTarget || !cloneName.trim()) return;
    setCloning(true);
    setCloneError(null);
    try {
      const item = await cloneReport(cloneTarget.report_id, cloneName.trim());
      setCloneTarget(null);
      refresh();
      navigate(`/app/reports/${item.report_id}?edit=true`);
    } catch (err) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setCloneError((err as any)?.message ?? 'Failed to clone report');
    } finally {
      setCloning(false);
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

  const columns: ListTableColumn<ReportListItem>[] = [
    {
      key: 'name',
      label: 'Name',
      cellSx: { ...listTablePrimaryCellSx, width: '36%' },
      render: (report) => {
        const isDashboard = report.report_id === dashboardReportId;
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0, flexWrap: 'nowrap', overflow: 'hidden' }}>
            <Link
              component={RouterLink}
              to={`/app/reports/${report.report_id}`}
              underline="hover"
              color="inherit"
              fontWeight="medium"
              sx={{ flex: '1 1 auto', minWidth: 0, maxWidth: '100%', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            >
              {report.name}
            </Link>
            {report.pinned && (
              <Tooltip title="Pinned to sidebar">
                <Chip
                  icon={<PushPinIcon sx={{ fontSize: '0.85rem !important' }} />}
                  label="Pinned"
                  size="small"
                  color="primary"
                  variant="outlined"
                  sx={{ height: 20, fontSize: '0.7rem' }}
                />
              </Tooltip>
            )}
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
        );
      }
    },
    {
      key: 'visibility',
      label: 'Visibility',
      cellSx: { width: 104 },
      render: (report) => (
        <Tooltip title={report.access.scope === 'public' ? 'Visible to report readers' : 'Private to the owner'}>
          <Chip
            icon={
              report.access.scope === 'public'
                ? <PublicIcon sx={{ fontSize: '0.85rem !important' }} />
                : <LockIcon sx={{ fontSize: '0.85rem !important' }} />
            }
            label={report.access.scope === 'public' ? 'Public' : 'Draft'}
            size="small"
            color={report.access.scope === 'public' ? 'success' : 'default'}
            variant="outlined"
          />
        </Tooltip>
      )
    },
    {
      key: 'version',
      label: 'Version',
      hideBelow: 'sm',
      cellSx: { ...listTableSecondaryCellSx, width: 96 },
      render: (report) => `v${report.current_version}`
    },
    {
      key: 'updated_at',
      label: 'Last updated',
      hideBelow: 'md',
      cellSx: { ...listTableSecondaryCellSx, width: 200 },
      render: (report) => new Date(report.updated_at).toLocaleString()
    },
    {
      key: 'updated_by',
      label: 'Updated by',
      hideBelow: 'lg',
      cellSx: { ...listTableSecondaryCellSx, width: 150 },
      render: (report) => <UserDisplay userId={report.updated_by || report.created_by} />
    },
    {
      key: 'actions',
      align: 'right',
      cellSx: listTableActionColumnSx,
      render: (report) => {
        const isDashboard = report.report_id === dashboardReportId;
        const isOwner = currentUser?.user_id === report.created_by;
        return (
          <RowMenu
            report={report}
            isDashboard={isDashboard}
            onSetDashboard={() => handleSetDashboard(report.report_id)}
            onPin={() => handlePin(report.report_id, !report.pinned)}
            onEdit={() => navigate(`/app/reports/${report.report_id}?edit=true`)}
            onHistory={() => navigate(`/app/reports/${report.report_id}/history`, { state: { fromLabel: 'Reports' } satisfies BackState })}
            onClone={() => handleCloneOpen(report)}
            onToggleAccess={() => handleToggleAccess(report)}
            onDelete={() => setDeleteTarget(report)}
            isOwner={isOwner}
            hasPermission={hasPermission}
          />
        );
      }
    }
  ];

  return (
    <>
      <Helmet>
        <title>Reports | Seizu</title>
      </Helmet>
      <Box sx={pageContentSx}>
        <Box
          sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}
        >
          <Typography variant="h1">Reports</Typography>
          {!permissionsLoading && hasPermission('reports:write') && (
            <Button variant="contained" startIcon={<Add />} onClick={() => setCreateOpen(true)}>
              New report
            </Button>
          )}
        </Box>

        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        )}

        {error && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Error />
            <Typography>Failed to load reports</Typography>
          </Box>
        )}

        {!loading && !error && (
          <ListTable
            rows={reports}
            columns={columns}
            getRowKey={(report) => report.report_id}
            emptyMessage="No reports yet. Create one above."
          />
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

      {/* Clone dialog */}
      <Dialog
        open={!!cloneTarget}
        onClose={() => setCloneTarget(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Clone report</DialogTitle>
        <DialogContent>
          {cloneError && (
            <Box sx={{ mb: 2 }}>
              <Typography color="error">{cloneError}</Typography>
            </Box>
          )}
          <TextField
            autoFocus
            fullWidth
            label="New report name"
            value={cloneName}
            onChange={(e) => setCloneName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCloneConfirm()}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCloneTarget(null)} disabled={cloning}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleCloneConfirm}
            disabled={cloning || !cloneName.trim()}
          >
            {cloning ? <CircularProgress size={20} /> : 'Clone'}
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
