import { useEffect } from 'react';
import PropTypes from 'prop-types';
import { Typography } from '@mui/material';
import Loader from 'react-loader-spinner';
import { useLazyReadCypher } from 'use-neo4j';
import Error from '@mui/icons-material/Error';
import OncallTable from 'src/components/reports/OncallTable';

export default function CypherOncallTable({
  cypher,
  params,
  caption,
  needInputs,
  enabled
}) {
  const [runQuery, { loading, error, records }] = useLazyReadCypher(cypher);

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
    return <Loader type="ThreeDots" color="#2BAD60" height="50" width="50" />;
  }

  const userIds = [];
  const escalationPolicyIds = [];
  const scheduleIds = [];
  records.forEach((record) => {
    if (record.keys.includes('user_id')) {
      userIds.push(record.get('user_id'));
    } else if (record.keys.includes('escalation_policy_id')) {
      escalationPolicyIds.push(record.get('escalation_policy_id'));
    } else if (record.keys.includes('schedule_id')) {
      scheduleIds.push(record.get('schedule_id'));
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

CypherOncallTable.propTypes = {
  cypher: PropTypes.string,
  params: PropTypes.object,
  caption: PropTypes.string,
  needInputs: PropTypes.array,
  enabled: PropTypes.bool
};
