import { useEffect } from 'react';
import { Typography } from '@mui/material';
import { ThreeDots } from 'react-loader-spinner';
import Error from '@mui/icons-material/Error';
import { useLazyCypherQuery } from 'src/hooks/useCypherQuery';
import OncallTable from 'src/components/reports/OncallTable';

interface CypherOncallTableProps {
  cypher?: string;
  params?: Record<string, unknown>;
  caption?: string;
  needInputs?: string[];
  enabled?: boolean;
}

export default function CypherOncallTable({
  cypher,
  params,
  caption,
  needInputs,
  enabled
}: CypherOncallTableProps) {
  const [runQuery, { loading, error, records }] = useLazyCypherQuery(cypher);

  useEffect(() => {
    if (enabled === true) {
      runQuery(params);
    }
  }, [cypher, params]);

  if (enabled === false) {
    return (
      <Typography variant="body2">
        Pagerduty is not enabled in the backend.
      </Typography>
    );
  }
  if (cypher === undefined) {
    return (
      <>
        <Error />
        <Typography variant="body2">Missing cypher query</Typography>
      </>
    );
  }

  if (needInputs !== undefined && needInputs.length > 0) {
    return (
      <div style={{ height: 400, width: '100%' }}>
        <Typography variant="body2">
          Please set {needInputs.join(', ')}
        </Typography>
      </div>
    );
  }

  if (error) {
    return (
      <Typography variant="body2">
        Failed to load data from backend, please reload.
      </Typography>
    );
  }

  if (loading || records === undefined) {
    return <ThreeDots color="#2BAD60" height="50" width="50" />;
  }

  const userIds: string[] = [];
  const escalationPolicyIds: string[] = [];
  const scheduleIds: string[] = [];
  records.forEach((record) => {
    if ('user_id' in record) {
      userIds.push(record['user_id'] as string);
    } else if ('escalation_policy_id' in record) {
      escalationPolicyIds.push(record['escalation_policy_id'] as string);
    } else if ('schedule_id' in record) {
      scheduleIds.push(record['schedule_id'] as string);
    }
  });

  if (
    userIds.length === 0 &&
    escalationPolicyIds.length === 0 &&
    scheduleIds.length === 0
  ) {
    return <Typography variant="body2">No on-calls found.</Typography>;
  }

  return (
    <OncallTable
      userIds={userIds}
      escalationPolicyIds={escalationPolicyIds}
      scheduleIds={scheduleIds}
      caption={caption}
    />
  );
}
