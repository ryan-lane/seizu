import { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { Box, Button, Typography } from '@mui/material';
import { ThreeDots } from 'react-loader-spinner';
import Error from '@mui/icons-material/Error';
import EditIcon from '@mui/icons-material/Edit';
import HistoryIcon from '@mui/icons-material/History';

import ReportView from 'src/components/ReportView';
import EditableReportView from 'src/components/EditableReportView';
import { useReport, useReportsMutations } from 'src/hooks/useReportsApi';
import { Report } from 'src/config.context';

function Reports() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [editMode, setEditMode] = useState(searchParams.get('edit') === 'true');
  const [displayedReport, setDisplayedReport] = useState<Report | undefined>(undefined);
  const [displayedName, setDisplayedName] = useState<string | undefined>(undefined);

  const { report, name, loading, error } = useReport(id);
  const { saveReportVersion } = useReportsMutations();

  useEffect(() => {
    if (report) setDisplayedReport(report);
    if (name) setDisplayedName(name);
  }, [report, name]);

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
    const version = await saveReportVersion(id, updatedReport, comment || undefined);
    setDisplayedReport(version.config);
    setDisplayedName(version.name);
    setEditMode(false);
    // Navigate back to view mode (clears ?edit param)
    navigate(`/app/reports/${id}`, { replace: true });
  }

  if (loading && !displayedReport) {
    return <ThreeDots color="#2BAD60" height="100" width="100" />;
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

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 3, pt: 2 }}>
        <Button
          variant="outlined"
          size="small"
          startIcon={<HistoryIcon />}
          onClick={() => navigate(`/app/reports/${id}/history`)}
        >
          History
        </Button>
        <Button
          variant="outlined"
          size="small"
          startIcon={<EditIcon />}
          onClick={handleEnterEdit}
        >
          Edit report
        </Button>
      </Box>
      <ReportView report={displayedReport} title={displayedName} />
    </Box>
  );
}

export default Reports;
