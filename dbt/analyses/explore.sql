SELECT
  {{ dimension }} AS label,
  SUM({{ measure_expr }}) AS value
FROM {{ relation }}
WHERE {{ metric_filter }}
  AND {{ date_filter }}
GROUP BY {{ dimension }}
ORDER BY value DESC
LIMIT {{ n }}