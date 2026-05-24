export function parseApiTimestamp(value: string) {
  const hasTimezone = /(?:z|[+-]\d{2}:?\d{2})$/i.test(value);
  const sqliteTimestamp = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(value);

  if (sqliteTimestamp && !hasTimezone) {
    return new Date(`${value.replace(' ', 'T')}Z`);
  }

  return new Date(value);
}
