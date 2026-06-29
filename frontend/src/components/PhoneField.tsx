import { Stack, TextField } from "@mui/material";

export const DEFAULT_PHONE_COUNTRY_CODE = "+91";

export const COUNTRY_CODES = [
  "+91",
  "+1",
  "+44",
  "+61",
  "+64",
  "+353",
  "+49",
  "+33",
  "+39",
  "+34",
  "+31",
  "+46",
  "+47",
  "+45",
  "+41",
  "+971",
  "+65",
  "+852",
  "+81",
  "+82",
  "+86",
] as const;

export function formatPhoneDisplay(countryCode: string | null | undefined, phone: string | null | undefined) {
  const loc = (phone ?? "").trim();
  if (!loc) return "—";
  const cc = (countryCode ?? "").trim();
  return cc ? `${cc} ${loc}` : loc;
}

type PhoneFieldProps = {
  countryCode: string;
  phone: string;
  onCountryCodeChange: (value: string) => void;
  onPhoneChange: (value: string) => void;
  disabled?: boolean;
  required?: boolean;
  defaultCountryCode?: string;
};

export function PhoneField({
  countryCode,
  phone,
  onCountryCodeChange,
  onPhoneChange,
  disabled,
  required,
  defaultCountryCode = DEFAULT_PHONE_COUNTRY_CODE,
}: PhoneFieldProps) {
  return (
    <Stack direction="row" spacing={1}>
      <TextField
        label="Country"
        select
        SelectProps={{ native: true }}
        value={countryCode || defaultCountryCode}
        onChange={(e) => onCountryCodeChange(e.target.value)}
        disabled={disabled}
        sx={{ minWidth: 100 }}
      >
        {COUNTRY_CODES.map((cc) => (
          <option key={cc} value={cc}>
            {cc}
          </option>
        ))}
      </TextField>
      <TextField
        label="Phone"
        value={phone}
        onChange={(e) => onPhoneChange(e.target.value)}
        fullWidth
        disabled={disabled}
        required={required}
        placeholder="Local number"
      />
    </Stack>
  );
}
