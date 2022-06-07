import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { trackPromise } from 'react-promise-tracker';
import { Typography } from '@mui/material';
import MUIDataTable from 'mui-datatables';

export default function OncallTable({
  userIds,
  escalationPolicyIds,
  scheduleIds,
  caption,
  enabled
}) {
  const [oncalls, setOncalls] = useState({});
  const [error, setError] = useState();

  const getOncalls = () => {
    const requestOptions = {
      method: 'GET',
      headers: {
        'Content-Type': 'Application/json'
      }
    };
    const searchParams = new URLSearchParams('');
    if (userIds !== undefined && userIds.length > 0) {
      searchParams.append('user_ids', userIds);
    } else if (
      escalationPolicyIds !== undefined &&
      escalationPolicyIds.length > 0
    ) {
      searchParams.append('escalation_policy_ids', escalationPolicyIds);
    } else if (scheduleIds !== undefined && scheduleIds.length > 0) {
      searchParams.append('schedule_ids', scheduleIds);
    }
    return fetch(
      `/api/v1/pagerduty/oncalls?${searchParams.toString()}`,
      requestOptions
    );
  };

  useEffect(() => {
    if (enabled === true) {
      trackPromise(
        getOncalls()
          .then((res) => res.json())
          .then(
            (result) => {
              setOncalls(result.oncalls);
            },
            (err) => {
              console.log('Error fetching oncalls', error);
              setError(err);
            }
          )
      );
    }
  }, [userIds, escalationPolicyIds, scheduleIds]);

  if (error) {
    console.log(error);
    return (
      <Typography variant="body2">
        Failed to load requested data, please reload.
      </Typography>
    );
  }

  if (enabled === false) {
    return (
      <Typography variant="body2">
        Pagerduty support is not enabled in the backend.
      </Typography>
    );
  }

  if (oncalls === undefined || oncalls === null || oncalls.length === 0) {
    return <Typography variant="body2">No oncalls found.</Typography>;
  }

  const columns = [
    {
      name: 'user',
      label: 'User'
    },
    {
      name: 'schedule',
      label: 'Schedule'
    },
    {
      name: 'escalation_policy',
      label: 'Escalation Policy'
    },
    {
      name: 'escalation_level',
      label: 'Escalation Level'
    },
    {
      name: 'start',
      label: 'Start'
    },
    {
      name: 'end',
      label: 'End'
    }
  ];

  const mungedOncalls = [];
  for (let i = 0; i < oncalls.length; i++) {
    const data = oncalls[i];
    const mungedData = {
      user: data.user?.summary,
      schedule: data.schedule?.summary,
      escalation_policy: data.escalation_policy?.summary,
      escalation_level: data.escalation_level,
      start: data.start,
      end: data.end
    };
    mungedOncalls.push(mungedData);
  }

  return (
    <>
      <Typography gutterBottom variant="h4">
        {caption}
      </Typography>
      <MUIDataTable
        data={mungedOncalls}
        columns={columns}
        options={{ responsive: 'simple', selectableRows: 'none', print: false }}
      />
    </>
  );
}

OncallTable.propTypes = {
  userIds: PropTypes.array,
  escalationPolicyIds: PropTypes.array,
  scheduleIds: PropTypes.array,
  caption: PropTypes.string,
  enabled: PropTypes.bool
};
