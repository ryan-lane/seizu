import { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Helmet } from 'react-helmet';
import {
  Box,
  Button,
  CircularProgress,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Tooltip,
  Typography
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import HistoryIcon from '@mui/icons-material/History';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import RestoreIcon from '@mui/icons-material/Restore';
import Error from '@mui/icons-material/Error';
import {
  ToolVersion,
  useToolVersionsList,
  useToolMutations
} from 'src/hooks/useToolsetsApi';
import ListTable, {
  ListTableColumn,
  listTableActionColumnSx,
  listTableSecondaryCellSx
} from 'src/components/ListTable';
import ToolDetailDialog, { ToolViewData } from 'src/components/ToolDetailDialog';
import UserDisplay from 'src/components/UserDisplay';
import { usePermissions } from 'src/hooks/usePermissions';
import type { BackState } from 'src/navigation';
import { pageContentSx } from 'src/theme/layout';

const savedColumnSx = { ...listTableSecondaryCellSx, width: 180 };
const authorColumnSx = { ...listTableSecondaryCellSx, width: 150 };
const commentColumnSx = { ...listTableSecondaryCellSx, width: '28%' };

// ---------------------------------------------------------------------------
// Per-row overflow menu
// ---------------------------------------------------------------------------

interface RowMenuProps {
  version: ToolVersion;
  isCurrent: boolean;
  onRestore: () => void;
  onDetail: () => void;
}

function RowMenu({ isCurrent, onRestore, onDetail }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const hasPermission = usePermissions();
  const close = () => setAnchor(null);

  const canWrite = hasPermission('tools:write');
  const restoreDisabled = isCurrent || !canWrite;
  const restoreTooltip = isCurrent
    ? 'This is already the current version'
    : !canWrite
      ? 'You do not have permission to restore tool versions'
      : '';

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
        <MenuItem onClick={() => { onDetail(); close(); }}>
          <ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon>
          <ListItemText>View detail</ListItemText>
        </MenuItem>

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

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function ToolHistory() {
  const { toolsetId, toolId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { fromLabel } = (location.state ?? {}) as BackState;

  const { versions, loading, error } = useToolVersionsList(toolsetId ?? null, toolId ?? null);
  const mutations = useToolMutations(toolsetId ?? '');
  const [detailData, setDetailData] = useState<ToolViewData | null>(null);

  const sorted = [...versions].sort((a, b) => b.version - a.version);
  const latestVersion = sorted[0]?.version;
  const toolName = sorted[0]?.name;
  const columns: ListTableColumn<ToolVersion>[] = [
    {
      key: 'version',
      label: 'Version',
      cellSx: { width: 120 },
      render: (version) => {
        const isCurrent = version.version === latestVersion;
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography
              fontWeight={isCurrent ? 'bold' : 'medium'}
              sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
              onClick={() =>
                setDetailData({
                  name: version.name,
                  version: version.version,
                  description: version.description,
                  cypher: version.cypher,
                  parameters: version.parameters,
                  enabled: version.enabled
                })
              }
            >
              v{version.version}
            </Typography>
            {isCurrent && (
              <Typography component="span" variant="caption" color="primary">
                current
              </Typography>
            )}
          </Box>
        );
      }
    },
    {
      key: 'name',
      label: 'Name',
      cellSx: { width: '24%' },
      render: (version) => version.name
    },
    {
      key: 'saved',
      label: 'Saved',
      hideBelow: 'sm',
      cellSx: savedColumnSx,
      render: (version) => new Date(version.created_at).toLocaleString()
    },
    {
      key: 'created_by',
      label: 'Created by',
      hideBelow: 'md',
      cellSx: authorColumnSx,
      render: (version) => <UserDisplay userId={version.created_by} />
    },
    {
      key: 'comment',
      label: 'Comment',
      hideBelow: 'lg',
      cellSx: commentColumnSx,
      render: (version) => version.comment || '—'
    },
    {
      key: 'actions',
      align: 'right',
      cellSx: listTableActionColumnSx,
      render: (version) => (
        <RowMenu
          version={version}
          isCurrent={version.version === latestVersion}
          onRestore={() => handleRestore(version)}
          onDetail={() =>
            setDetailData({
              name: version.name,
              version: version.version,
              description: version.description,
              cypher: version.cypher,
              parameters: version.parameters,
              enabled: version.enabled
            })
          }
        />
      )
    }
  ];

  async function handleRestore(version: ToolVersion) {
    if (!toolId) return;
    await mutations.updateTool(toolId, {
      name: version.name,
      description: version.description,
      cypher: version.cypher,
      parameters: version.parameters,
      enabled: version.enabled,
      comment: `Restored from version ${version.version}`
    });
    navigate(`/app/toolsets/${toolsetId}/tools`);
  }

  return (
    <>
      <Helmet>
        <title>{toolName ? `History – ${toolName} | Seizu` : 'History | Seizu'}</title>
      </Helmet>
      <Box sx={pageContentSx}>
        {fromLabel && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Button
              size="small"
              startIcon={<ArrowBackIcon />}
              onClick={() => navigate(-1)}
            >
              Back to {fromLabel}
            </Button>
          </Box>
        )}

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
          <HistoryIcon color="action" />
          <Typography variant="h1">
            Version history{toolName ? ` – ${toolName}` : ''}
          </Typography>
        </Box>

        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        )}

        {error && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Error />
            <Typography>Failed to load version history</Typography>
          </Box>
        )}

        {!loading && !error && (
          <ListTable
            rows={sorted}
            columns={columns}
            getRowKey={(version) => version.version}
            emptyMessage="No versions found."
            pagination={false}
          />
        )}
      </Box>

      <ToolDetailDialog
        open={!!detailData}
        onClose={() => setDetailData(null)}
        data={detailData}
      />
    </>
  );
}

export default ToolHistory;
