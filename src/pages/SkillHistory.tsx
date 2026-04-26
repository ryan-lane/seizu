import { Box, Button, CircularProgress, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import HistoryIcon from '@mui/icons-material/History';
import { useNavigate, useParams } from 'react-router-dom';
import { Helmet } from 'react-helmet';
import { useSkillVersionsList } from 'src/hooks/useSkillsetsApi';
import UserDisplay from 'src/components/UserDisplay';

function SkillHistory() {
  const { skillsetId, skillId } = useParams();
  const navigate = useNavigate();
  const { versions, loading, error } = useSkillVersionsList(skillsetId ?? null, skillId ?? null);
  const name = versions[0]?.name;

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
            <TableHead><TableRow><TableCell>Version</TableCell><TableCell>Saved</TableCell><TableCell>Created By</TableCell><TableCell>Comment</TableCell></TableRow></TableHead>
            <TableBody>
              {versions.map((v) => (
                <TableRow key={v.version} hover>
                  <TableCell>{`v${v.version}`}</TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>{new Date(v.created_at).toLocaleString()}</TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}><UserDisplay userId={v.created_by} /></TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>{v.comment || '-'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}

export default SkillHistory;
