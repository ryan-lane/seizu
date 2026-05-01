import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Divider,
  Paper,
  Skeleton
} from '@mui/material';

interface CaptionProps {
  caption?: string;
}

function HeaderSkeleton({ caption }: CaptionProps) {
  return (
    <CardHeader
      title={caption || <Skeleton variant="text" width={180} height={32} />}
      sx={{ textAlign: 'center' }}
    />
  );
}

export function CountPanelSkeleton({ caption }: CaptionProps) {
  return (
    <Card data-testid="count-panel-loading-skeleton" sx={{ minHeight: 150 }}>
      <HeaderSkeleton caption={caption} />
      <Divider />
      <CardContent sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
        <Skeleton variant="text" width={96} height={56} />
      </CardContent>
    </Card>
  );
}

export function ProgressPanelSkeleton({ caption }: CaptionProps) {
  return (
    <Card data-testid="progress-panel-loading-skeleton" sx={{ minHeight: 300 }}>
      <HeaderSkeleton caption={caption} />
      <Divider />
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
      <HeaderSkeleton caption={caption} />
      <Divider />
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
