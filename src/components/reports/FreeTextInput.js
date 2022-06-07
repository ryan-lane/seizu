import PropTypes from 'prop-types';
import { TextField } from '@mui/material';
import { setQueryStringValue } from 'src/components/QueryString';

export default function FreeTextInput({
  inputId,
  inputDefault,
  labelName,
  value,
  setValue
}) {
  return (
    <TextField
      onChange={(event) => {
        if (event.target.value === null || event.target.value === undefined) {
          setValue({ ...value, [inputId]: { label: '', value: inputDefault } });
          setQueryStringValue(inputId, inputDefault);
        } else {
          setValue({
            ...value,
            [inputId]: { label: '', value: event.target.value }
          });
          setQueryStringValue(inputId, event.target.value);
        }
      }}
      id={inputId}
      label={labelName}
      variant="outlined"
      fullWidth
    />
  );
}

FreeTextInput.propTypes = {
  inputId: PropTypes.string,
  inputDefault: PropTypes.string,
  labelName: PropTypes.string,
  value: PropTypes.object,
  setValue: PropTypes.func
};
