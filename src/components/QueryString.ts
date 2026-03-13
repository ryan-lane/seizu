import qs from 'query-string';

const setQueryStringWithoutPageReload = (qsValue: string): void => {
  const newurl = `${window.location.protocol}//${window.location.host}${window.location.pathname}${qsValue}`;
  window.history.pushState({ path: newurl }, '', newurl);
};

export const getQueryStringValue = (
  key: string,
  queryString: string = window.location.search
): string | (string | null)[] | null | undefined => {
  const values = qs.parse(queryString);
  return values[key];
};

export const setQueryStringValue = (
  key: string,
  value: string | undefined,
  queryString: string = window.location.search
): void => {
  const values = qs.parse(queryString);
  const newQsValue = qs.stringify({
    ...values,
    [key]: value
  });
  setQueryStringWithoutPageReload(`?${newQsValue}`);
};
