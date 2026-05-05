import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Divider,
  Paper,
  Skeleton,
  useTheme
} from '@mui/material';

interface CaptionProps {
  caption?: string;
}

function HeaderSkeleton({ caption }: CaptionProps) {
  if (!caption) return null;
  return (
    <CardHeader
      title={caption}
      sx={{ textAlign: 'center' }}
    />
  );
}

export function CountPanelSkeleton({ caption }: CaptionProps) {
  return (
    <Card data-testid="count-panel-loading-skeleton" sx={{ minHeight: 150 }}>
      {caption && (
        <>
          <HeaderSkeleton caption={caption} />
          <Divider />
        </>
      )}
      <CardContent sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
        <Skeleton variant="text" width={96} height={56} />
      </CardContent>
    </Card>
  );
}

export function ProgressPanelSkeleton({ caption }: CaptionProps) {
  return (
    <Card data-testid="progress-panel-loading-skeleton" sx={{ minHeight: 300 }}>
      {caption && (
        <>
          <HeaderSkeleton caption={caption} />
          <Divider />
        </>
      )}
      <CardContent sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
        <Skeleton variant="text" width={150} height={56} />
      </CardContent>
      <CardContent sx={{ display: 'flex', justifyContent: 'center', pt: 0 }}>
        <Skeleton variant="circular" width={100} height={100} />
      </CardContent>
    </Card>
  );
}

export function ChartPanelSkeleton({
  caption,
  variant
}: CaptionProps & { variant: 'bar' | 'pie' }) {
  return (
    <Card data-testid={`${variant}-panel-loading-skeleton`} sx={{ minHeight: 410 }}>
      {caption && (
        <>
          <HeaderSkeleton caption={caption} />
          <Divider />
        </>
      )}
      <Box sx={{ height: 350, p: 2, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {variant === 'pie' ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Skeleton variant="circular" width={220} height={220} />
            <Box sx={{ display: 'grid', gap: 1 }}>
              <Skeleton variant="text" width={120} height={22} />
              <Skeleton variant="text" width={100} height={22} />
              <Skeleton variant="text" width={140} height={22} />
            </Box>
          </Box>
        ) : (
          <Box sx={{ width: '100%', height: '100%', display: 'flex', alignItems: 'flex-end', gap: 1.5, px: 4, pb: 4 }}>
            {[45, 72, 54, 88, 64, 38, 78].map((height, index) => (
              // eslint-disable-next-line react/no-array-index-key
              <Skeleton key={index} variant="rectangular" width="12%" height={`${height}%`} sx={{ borderRadius: 1 }} />
            ))}
          </Box>
        )}
      </Box>
    </Card>
  );
}

export function GraphPanelSkeleton({
  caption,
  fillHeight = false
}: CaptionProps & { fillHeight?: boolean }) {
  return (
    <Card
      data-testid="graph-panel-loading-skeleton"
      sx={fillHeight ? { height: '100%', display: 'flex', flexDirection: 'column' } : { minHeight: 500 }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', minHeight: 48, px: 2, gap: 2 }}>
        <Skeleton variant="text" width={64} height={28} />
        <Skeleton variant="text" width={58} height={28} />
        <Skeleton variant="text" width={44} height={28} />
        {caption && <Box sx={{ ml: 'auto' }}><Skeleton variant="text" width={160} height={28} /></Box>}
      </Box>
      <Divider />
      <Box sx={{ flex: fillHeight ? 1 : 'none', height: fillHeight ? 'auto' : 450, minHeight: fillHeight ? 0 : undefined, display: 'flex' }}>
        <Box sx={{ flex: 1, p: 2 }}>
          <Skeleton variant="rectangular" width="100%" height="100%" sx={{ minHeight: 320 }} />
        </Box>
        <Divider orientation="vertical" flexItem />
        <Box sx={{ width: 280, p: 2, display: { xs: 'none', md: 'grid' }, alignContent: 'start', gap: 1 }}>
          <Skeleton variant="text" width={120} height={28} />
          <Skeleton variant="text" width="90%" height={22} />
          <Skeleton variant="text" width="78%" height={22} />
          <Skeleton variant="text" width="84%" height={22} />
        </Box>
      </Box>
    </Card>
  );
}

export function VerticalTableSkeleton() {
  return (
    <Box data-testid="vertical-table-loading-skeleton">
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Skeleton variant="text" width={180} height={32} />
        <Skeleton variant="circular" width={32} height={32} />
      </Box>
      <Divider />
      <Paper sx={{ p: 2, mt: 1 }}>
        {Array.from({ length: 7 }).map((_, index) => (
          // eslint-disable-next-line react/no-array-index-key
          <Box key={index} sx={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: 2, py: 1 }}>
            <Skeleton variant="text" height={22} />
            <Skeleton variant="text" height={22} />
          </Box>
        ))}
      </Paper>
    </Box>
  );
}

/** Compact skeleton used inside the edit-mode panel card. Fills available height. */
export function EditPanelSkeleton({ type }: { type: string }) {
  const theme = useTheme();
  const nodeColor = theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.13)' : 'rgba(0,0,0,0.11)';
  const edgeColor = theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)';

  switch (type) {
    case 'count':
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
          <Skeleton animation={false} variant="text" width="40%" height={40} />
        </Box>
      );
    case 'progress':
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', gap: 0.75 }}>
          <Skeleton animation={false} variant="text" width="50%" height={22} />
          <Skeleton animation={false} variant="circular" width={56} height={56} />
        </Box>
      );
    case 'bar':
      return (
        <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 0.75, height: '100%', px: 0.5, pb: 0.5 }}>
          {[50, 75, 55, 90, 65, 40, 80].map((h, index) => (
            // eslint-disable-next-line react/no-array-index-key
            <Skeleton animation={false} key={index} variant="rectangular" sx={{ flex: 1, height: `${h}%`, borderRadius: 0.5 }} />
          ))}
        </Box>
      );
    case 'pie':
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', gap: 1.5, px: 0.5 }}>
          <Skeleton
            animation={false}
            variant="circular"
            sx={{ width: '55%', height: 'auto', aspectRatio: '1', maxWidth: 150, flexShrink: 0 }}
          />
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75, justifyContent: 'center' }}>
            <Skeleton animation={false} variant="text" width={72} height={14} />
            <Skeleton animation={false} variant="text" width={58} height={14} />
            <Skeleton animation={false} variant="text" width={68} height={14} />
            <Skeleton animation={false} variant="text" width={44} height={14} />
          </Box>
        </Box>
      );
    case 'graph':
      return (
        <Box sx={{ height: '100%', px: 0.5, pb: 0.5 }}>
          <svg width="100%" height="100%" viewBox="0 0 200 160" preserveAspectRatio="xMidYMid meet">
            <line x1="38" y1="42" x2="98" y2="20" stroke={edgeColor} strokeWidth="2" />
            <line x1="98" y1="20" x2="158" y2="38" stroke={edgeColor} strokeWidth="2" />
            <line x1="38" y1="42" x2="65" y2="105" stroke={edgeColor} strokeWidth="2" />
            <line x1="158" y1="38" x2="138" y2="112" stroke={edgeColor} strokeWidth="2" />
            <line x1="65" y1="105" x2="138" y2="112" stroke={edgeColor} strokeWidth="2" />
            <line x1="65" y1="105" x2="30" y2="138" stroke={edgeColor} strokeWidth="2" />
            <circle cx="38" cy="42" r="11" fill={nodeColor} />
            <circle cx="98" cy="20" r="8" fill={nodeColor} />
            <circle cx="158" cy="38" r="13" fill={nodeColor} />
            <circle cx="65" cy="105" r="10" fill={nodeColor} />
            <circle cx="138" cy="112" r="9" fill={nodeColor} />
            <circle cx="30" cy="138" r="7" fill={nodeColor} />
          </svg>
        </Box>
      );
    case 'table':
      return (
        <Box sx={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column', px: 0.5 }}>
          <Skeleton animation={false} variant="rectangular" width="100%" height={26} sx={{ borderRadius: 0.5, flexShrink: 0, mb: 0.5 }} />
          <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', justifyContent: 'space-around' }}>
            {[0, 1, 2, 3, 4, 5, 6].map((index) => (
              // eslint-disable-next-line react/no-array-index-key
              <Box key={index} sx={{ display: 'flex', gap: 0.5 }}>
                <Skeleton animation={false} variant="rectangular" sx={{ flex: 2 }} height={20} />
                <Skeleton animation={false} variant="rectangular" sx={{ flex: 3 }} height={20} />
                <Skeleton animation={false} variant="rectangular" sx={{ flex: 1 }} height={20} />
              </Box>
            ))}
          </Box>
        </Box>
      );
    case 'vertical-table':
      return (
        <Box sx={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column', px: 0.5 }}>
          <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', justifyContent: 'space-around' }}>
            {[0, 1, 2, 3, 4, 5, 6].map((index) => (
              // eslint-disable-next-line react/no-array-index-key
              <Box key={index} sx={{ display: 'grid', gridTemplateColumns: '40% 1fr', gap: 1 }}>
                <Skeleton animation={false} variant="rectangular" height={20} />
                <Skeleton animation={false} variant="rectangular" height={20} />
              </Box>
            ))}
          </Box>
        </Box>
      );
    case 'markdown':
      return (
        <Box sx={{ height: '100%', overflow: 'hidden', px: 0.5, display: 'flex', flexDirection: 'column', gap: 0 }}>
          {/* heading */}
          <Skeleton animation={false} variant="text" width="55%" height={20} sx={{ mb: 0.5 }} />
          {/* paragraph 1 */}
          <Skeleton animation={false} variant="text" width="97%" height={13} />
          <Skeleton animation={false} variant="text" width="92%" height={13} />
          <Skeleton animation={false} variant="text" width="95%" height={13} />
          <Skeleton animation={false} variant="text" width="48%" height={13} sx={{ mb: 1 }} />
          {/* paragraph 2 */}
          <Skeleton animation={false} variant="text" width="94%" height={13} />
          <Skeleton animation={false} variant="text" width="89%" height={13} />
          <Skeleton animation={false} variant="text" width="60%" height={13} sx={{ mb: 1 }} />
          {/* paragraph 3 */}
          <Skeleton animation={false} variant="text" width="96%" height={13} />
          <Skeleton animation={false} variant="text" width="78%" height={13} />
        </Box>
      );
    default:
      return (
        <Box sx={{ height: '100%', px: 0.5, pb: 0.5 }}>
          <Skeleton animation={false} variant="rectangular" width="100%" height="100%" sx={{ borderRadius: 0.5 }} />
        </Box>
      );
  }
}
