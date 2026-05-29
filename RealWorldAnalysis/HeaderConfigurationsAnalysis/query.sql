SELECT
  page,
  url,
  client,
  root_page,
  is_root_page,
  date,
  rank,
  ARRAY(
    SELECT value 
    FROM UNNEST(response_headers) 
    WHERE LOWER(name) = 'content-security-policy' 
      AND value IS NOT NULL
  ) AS csp_headers,
  ARRAY(
    SELECT value 
    FROM UNNEST(response_headers) 
    WHERE LOWER(name) = 'x-frame-options' 
      AND value IS NOT NULL
  ) AS xfo_headers
FROM
  `httparchive.latest.requests`
WHERE
  is_root_page
  AND page = url
  AND client = 'mobile'
  AND date = "2026-05-01"
  AND rank <= 1000000