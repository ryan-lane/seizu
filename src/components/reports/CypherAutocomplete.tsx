import { useEffect } from 'react';
import { Typography, TextField, Autocomplete } from '@mui/material';
import { ThreeDots } from 'react-loader-spinner';
import { useLazyCypherQuery } from 'src/hooks/useCypherQuery';
import { setQueryStringValue } from 'src/components/QueryString';

interface AutocompleteOption {
  label?: string;
  value?: string;
}

interface CypherAutocompleteProps {
  cypher?: string;
  params?: Record<string, unknown>;
  inputId?: string;
  inputDefault?: AutocompleteOption;
  labelName?: string;
  value?: Record<string, AutocompleteOption | undefined>;
  setValue?: (val: Record<string, AutocompleteOption | undefined>) => void;
}

export default function CypherAutocomplete({
  cypher,
  params,
  inputId,
  inputDefault,
  labelName,
  value,
  setValue
}: CypherAutocompleteProps) {
  const [run, { loading, error, records }] = useLazyCypherQuery(cypher);

  useEffect(() => {
    run(params);
  }, [cypher, params]);

  if (error) {
    return (
      <Typography>Failed to load data from backend, please reload.</Typography>
    );
  }

  if (loading || records === undefined) {
    return <ThreeDots color="#2BAD60" height="50" width="50" />;
  }

  const mungedRecords: AutocompleteOption[] = records.map((record) => {
    const val: AutocompleteOption = {};
    if ('label' in record) {
      val.label = record['label'] as string;
    } else {
      val.label = record['value'] as string;
    }
    val.value = record['value'] as string;
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
      value={value?.[inputId || '']}
      onChange={(event, newValue) => {
        if (newValue === null || newValue === undefined) {
          setValue?.({ ...value, [inputId || '']: inputDefault });
          setQueryStringValue(inputId, inputDefault?.value);
        } else {
          setValue?.({ ...value, [inputId || '']: newValue });
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
