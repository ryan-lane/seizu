import { useEffect } from 'react';
import PropTypes from 'prop-types';
import { Typography, TextField, Autocomplete } from '@mui/material';
import Loader from 'react-loader-spinner';
import { useReadCypher } from 'use-neo4j';
import { setQueryStringValue } from 'src/components/QueryString';

export default function CypherAutocomplete({
  cypher,
  params,
  inputId,
  inputDefault,
  labelName,
  value,
  setValue
}) {
  const { loading, error, records, run } = useReadCypher(cypher, params);

  useEffect(() => {
    run(params);
  }, [cypher, params]);

  if (error) {
    return (
      <Typography>Failed to load data from backend, please reload.</Typography>
    );
  }

  if (loading || records === undefined) {
    return <Loader type="ThreeDots" color="#2BAD60" height="50" width="50" />;
  }

  const mungedRecords = records.map((record) => {
    const val = {};
    if (record.keys.includes('label')) {
      val.label = record.get('label');
    } else {
      val.label = record.get('value');
    }
    val.value = record.get('value');
    return val;
  });

  // Add an empty option, to handle the case of an empty default.
  if (inputDefault !== undefined) {
    mungedRecords.push(inputDefault);
  } else {
    mungedRecords.push({});
  }

  return (
    <Autocomplete
      value={value[inputId]}
      onChange={(event, newValue) => {
        if (newValue === null || newValue === undefined) {
          setValue({ ...value, [inputId]: inputDefault });
          setQueryStringValue(inputId, inputDefault?.value);
        } else {
          setValue({ ...value, [inputId]: newValue });
          setQueryStringValue(inputId, newValue?.value);
        }
      }}
      filterSelectedOptions
      selectOnFocus
      clearOnBlur
      handleHomeEndKeys
      id={inputId}
      getOptionLabel={(option) => option?.label || ''}
      options={mungedRecords}
      isOptionEqualToValue={(option, val) => {
        if (option?.value === val.value) {
          return true;
        }
        return false;
      }}
      renderInput={(selectParams) => (
        <TextField {...selectParams} label={labelName} variant="outlined" />
      )}
    />
  );
}

CypherAutocomplete.propTypes = {
  cypher: PropTypes.string,
  params: PropTypes.object,
  inputId: PropTypes.string,
  inputDefault: PropTypes.object,
  labelName: PropTypes.string,
  value: PropTypes.object,
  setValue: PropTypes.func
};
