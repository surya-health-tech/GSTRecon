/** IANA timezones offered in firm settings (keep in sync with backend STANDARD_IANA_TIMEZONES). */
export const TIMEZONE_OPTIONS = [
  "Asia/Kolkata",
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Berlin",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Australia/Sydney",
] as const;

export const DEFAULT_FIRM_TIMEZONE = "Asia/Kolkata";

export function normalizeFirmTimezone(tz: string | null | undefined): string {
  const raw = (tz || DEFAULT_FIRM_TIMEZONE).trim() || DEFAULT_FIRM_TIMEZONE;
  if ((TIMEZONE_OPTIONS as readonly string[]).includes(raw)) return raw;
  try {
    Intl.DateTimeFormat(undefined, { timeZone: raw });
    return raw;
  } catch {
    return DEFAULT_FIRM_TIMEZONE;
  }
}

/** YYYY-MM-DD for a date input in the given IANA timezone. */
export function ymdInTimezone(tz: string, at: Date = new Date()): string {
  const zone = normalizeFirmTimezone(tz);
  try {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: zone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(at);
  } catch {
    const d = at;
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }
}

export function firstOfMonthYmdInTimezone(tz: string, at: Date = new Date()): string {
  const ymd = ymdInTimezone(tz, at);
  return `${ymd.slice(0, 7)}-01`;
}

export function timezoneLabel(tz: string): string {
  return tz.replace(/_/g, " ");
}
