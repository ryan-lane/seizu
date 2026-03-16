import { TextField } from '@mui/material';
import { InputValue } from 'src/config.context';
import { setQueryStringValue } from 'src/components/QueryString';

interface FreeTextInputProps {
  inputId?: string;
  inputDefault?: InputValue;
  labelName?: string;
  value?: Record<string, InputValue | undefined>;
  setValue?: (val: Record<string, InputValue | undefined>) => void;
}

export default function FreeTextInput({
  inputId,
  inputDefault,
  labelName,
  value,
  setValue
}: FreeTextInputProps) {
  return (
    <TextField
      onChange={(event) => {
        if (event.target.value === null || event.target.value === undefined || event.target.value === '') {
          setValue?.({ ...value, [inputId || '']: inputDefault });
          setQueryStringValue(inputId, inputDefault?.value);
        } else {
          setValue?.({
            ...value,
            [inputId || '']: { label: '', value: event.target.value }
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
