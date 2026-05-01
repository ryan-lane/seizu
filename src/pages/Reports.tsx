import { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
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
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import Error from '@mui/icons-material/Error';
import EditIcon from '@mui/icons-material/Edit';
import HistoryIcon from '@mui/icons-material/History';
import LockIcon from '@mui/icons-material/Lock';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import PublicIcon from '@mui/icons-material/Public';

import ReportView from 'src/components/ReportView';
import EditableReportView from 'src/components/EditableReportView';
import { useReport, useReportsMutations } from 'src/hooks/useReportsApi';
import { Report } from 'src/config.context';
import { usePermissionState } from 'src/hooks/usePermissions';

function Reports() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { hasPermission, loading: permissionsLoading, currentUser } = usePermissionState();

  const [editMode, setEditMode] = useState(searchParams.get('edit') === 'true');
  const [displayedReport, setDisplayedReport] = useState<Report | undefined>(undefined);
  const [displayedName, setDisplayedName] = useState<string | undefined>(undefined);
  const [displayedAccessScope, setDisplayedAccessScope] = useState<'private' | 'public' | undefined>(undefined);
  const [displayedOwnerId, setDisplayedOwnerId] = useState<string | undefined>(undefined);
  const [displayedQueryCapabilities, setDisplayedQueryCapabilities] = useState<Record<string, string> | undefined>(undefined);

  const { report, name, reportVersion, queryCapabilities, loading, error } = useReport(id);
  const { saveReportVersion, cloneReport, updateReportAccess } = useReportsMutations();

  const [cloneOpen, setCloneOpen] = useState(false);
  const [cloneName, setCloneName] = useState('');
  const [cloning, setCloning] = useState(false);
  const [cloneError, setCloneError] = useState<string | null>(null);
  const [updatingAccess, setUpdatingAccess] = useState(false);
  const [actionsAnchor, setActionsAnchor] = useState<null | HTMLElement>(null);

  const handleCloneOpen = () => {
    setCloneName(`Copy of ${displayedName ?? ''}`);
    setCloneError(null);
    setCloneOpen(true);
  };

  const handleCloneConfirm = async () => {
    if (!id || !cloneName.trim()) return;
    setCloning(true);
    setCloneError(null);
    try {
      const item = await cloneReport(id, cloneName.trim());
      setCloneOpen(false);
      navigate(`/app/reports/${item.report_id}?edit=true`);
    } catch (err) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setCloneError((err as any)?.message ?? 'Failed to clone report');
    } finally {
      setCloning(false);
    }
  };

  useEffect(() => {
    if (report) {
      const reportName = name?.trim() || report.name;
      setDisplayedReport(reportName ? { ...report, name: reportName } : report);
    }
    if (name) setDisplayedName(name);
    if (reportVersion) {
      setDisplayedAccessScope(reportVersion.access.scope);
      setDisplayedOwnerId(reportVersion.report_created_by);
    }
    setDisplayedQueryCapabilities(queryCapabilities);
  }, [report, name, reportVersion, queryCapabilities]);

  // Sync edit param in URL
  useEffect(() => {
    if (editMode) {
      setSearchParams({ edit: 'true' }, { replace: true });
    } else {
      setSearchParams({}, { replace: true });
    }
  }, [editMode, setSearchParams]);

  function handleEnterEdit() {
    setEditMode(true);
  }

  function handleCancel() {
    setEditMode(false);
  }

  async function handleSave(updatedReport: Report, comment: string) {
    if (!id) return;
    const version = await saveReportVersion(id, updatedReport, comment || undefined, true);
    const savedName = updatedReport.name?.trim() || version.name;
    setDisplayedReport(savedName ? { ...version.config, name: savedName } : version.config);
    setDisplayedName(savedName);
    setDisplayedQueryCapabilities(version.query_capabilities);
    window.dispatchEvent(new Event('seizu:reports-updated'));
    setEditMode(false);
    // Navigate back to view mode (clears ?edit param)
    navigate(`/app/reports/${id}`, { replace: true });
  }

  async function handleToggleAccess() {
    if (!id || !displayedAccessScope) return;
    setUpdatingAccess(true);
    try {
      const updated = await updateReportAccess(id, displayedAccessScope === 'public' ? 'private' : 'public');
      setDisplayedAccessScope(updated.access.scope);
    } finally {
      setUpdatingAccess(false);
    }
  }

  if ((loading && !displayedReport) || permissionsLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if ((error || !displayedReport) && !loading) {
    return (
      <Box sx={{ p: 3, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Error />
        <Typography>Failed to load report</Typography>
      </Box>
    );
  }

  if (!displayedReport) return null;

  if (displayedQueryCapabilities === undefined) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  const isOwner = currentUser?.user_id === displayedOwnerId;
  const canUpdateAccess = hasPermission('reports:write') && isOwner;
  const canWriteReports = hasPermission('reports:write');
  const actionsMenuOpen = Boolean(actionsAnchor);

  const closeActionsMenu = () => {
    setActionsAnchor(null);
  };

  const secondaryActions = [
    {
      key: 'history',
      label: 'History',
      icon: <HistoryIcon fontSize="small" />,
      disabled: false,
      onClick: () => navigate(`/app/reports/${id}/history`)
    },
    ...(canWriteReports
      ? [
          {
            key: 'visibility',
            label: displayedAccessScope === 'public' ? 'Unpublish' : 'Publish',
            icon: updatingAccess
              ? <CircularProgress size={18} />
              : displayedAccessScope === 'public'
                ? <LockIcon fontSize="small" />
                : <PublicIcon fontSize="small" />,
            disabled: !canUpdateAccess || updatingAccess,
            onClick: handleToggleAccess
          },
          {
            key: 'clone',
            label: 'Clone',
            icon: <ContentCopyIcon fontSize="small" />,
            disabled: false,
            onClick: handleCloneOpen
          }
        ]
      : [])
  ];

  if (editMode) {
    return (
      <EditableReportView
        report={displayedReport}
        reportId={id ?? ''}
        onSave={handleSave}
        onCancel={handleCancel}
      />
    );
  }

  const reportActions = (
    <>
      {displayedAccessScope && (
        <Chip
          icon={displayedAccessScope === 'public' ? <PublicIcon /> : <LockIcon />}
          label={displayedAccessScope === 'public' ? 'Public' : 'Draft'}
          size="small"
          color={displayedAccessScope === 'public' ? 'success' : 'default'}
          variant="outlined"
          sx={{ alignSelf: 'center' }}
        />
      )}
      {canWriteReports && (
        <Button
          variant="contained"
          size="small"
          startIcon={<EditIcon />}
          onClick={handleEnterEdit}
        >
          Edit Report
        </Button>
      )}
      {secondaryActions.length === 1 ? (
        <Button
          variant="outlined"
          size="small"
          startIcon={secondaryActions[0].icon}
          disabled={secondaryActions[0].disabled}
          onClick={secondaryActions[0].onClick}
        >
          {secondaryActions[0].label}
        </Button>
      ) : (
        <>
          <Tooltip title="More actions">
            <IconButton
              aria-label="More actions"
              size="small"
              onClick={(event) => setActionsAnchor(event.currentTarget)}
            >
              <MoreVertIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Menu
            anchorEl={actionsAnchor}
            open={actionsMenuOpen}
            onClose={closeActionsMenu}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          >
            {secondaryActions.map((action) => (
              <MenuItem
                key={action.key}
                onClick={() => {
                  closeActionsMenu();
                  action.onClick();
                }}
                disabled={action.disabled}
              >
                <ListItemIcon>{action.icon}</ListItemIcon>
                <ListItemText>{action.label}</ListItemText>
              </MenuItem>
            ))}
          </Menu>
        </>
      )}
    </>
  );

  return (
    <Box>
      <ReportView
        report={displayedReport}
        title={displayedName}
        showTitle
        queryCapabilities={displayedQueryCapabilities}
        toolbarActions={reportActions}
      />

      <Dialog open={cloneOpen} onClose={() => setCloneOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Clone report</DialogTitle>
        <DialogContent>
          {cloneError && (
            <Typography color="error" sx={{ mb: 1 }}>
              {cloneError}
            </Typography>
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
          <Button onClick={() => setCloneOpen(false)} disabled={cloning}>
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
    </Box>
  );
}

export default Reports;
