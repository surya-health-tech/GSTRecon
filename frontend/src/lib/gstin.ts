/** Indian GSTIN (GST Number) format validation. */

export const GSTIN_REGEX = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;

export function normalizeGstin(value: string): string {
  return value.trim().toUpperCase();
}

export function isValidGstin(value: string): boolean {
  const gst = normalizeGstin(value);
  return gst.length === 15 && GSTIN_REGEX.test(gst);
}

export function gstinValidationMessage(value: string): string | null {
  const gst = normalizeGstin(value);
  if (!gst) return "GST Number is required";
  if (gst.length !== 15) return "GST Number must be exactly 15 characters";
  if (!GSTIN_REGEX.test(gst)) {
    return "Invalid GST Number format. Expected a valid 15-character GSTIN.";
  }
  return null;
}
