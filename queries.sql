-- name: load_discharge_data_view_diag_su
WITH dx AS (
  SELECT DISTINCT record_id, TRIM(diagnosis) AS substance
  FROM discharge_data_view_diag_su
  WHERE diagnosis IS NOT NULL AND TRIM(diagnosis) <> ''
)
SELECT
  dx.record_id,
  dx.substance,
  m.county, 
  m.city, 
  m.zip, 
  m.hawaii_residency,
  m.age_group, 
  m.sex, 
  REPLACE(TRIM(m.race_ethnicity), 'Black of African American', 'Black or African American') AS race_ethnicity,
  m.year
FROM dx
JOIN discharge_data_view_demographics_test m ON m.record_id = dx.record_id;


-- name: load_discharge_data_view_diag_mh
WITH dx AS (
  SELECT DISTINCT record_id, TRIM(diagnosis) AS diagnosis
  FROM discharge_data_view_diag_mh
  WHERE diagnosis IS NOT NULL AND TRIM(diagnosis) <> ''
)
SELECT
  dx.record_id,
  dx.diagnosis,
  m.county, 
  m.city, 
  m.zip, 
  m.hawaii_residency,
  m.age_group, 
  m.sex, 
  REPLACE(TRIM(m.race_ethnicity), 'Black of African American', 'Black or African American') AS race_ethnicity,
  m.year
FROM dx
JOIN discharge_data_view_demographics_test m ON m.record_id = dx.record_id;


-- name: load_polysubstance_data
WITH
dx_union AS (
  SELECT DISTINCT record_id, TRIM(diagnosis) AS substance
  FROM discharge_data_view_diag_su
  WHERE diagnosis IS NOT NULL AND TRIM(diagnosis) <> ''
),
poly_ids AS (
  -- polysubstance = ≥2 distinct substances
  SELECT record_id
  FROM dx_union
  GROUP BY record_id
  HAVING COUNT(DISTINCT substance) >= 2
)
SELECT
  u.record_id,
  u.substance,
  m.county, 
  m.city, 
  m.zip, 
  m.hawaii_residency,
  m.age_group, 
  m.sex, 
  REPLACE(TRIM(m.race_ethnicity), 'Black of African American', 'Black or African American') AS race_ethnicity,
  CAST(m.year AS INTEGER) AS year
FROM dx_union AS u
JOIN poly_ids AS p
  ON p.record_id = u.record_id
JOIN discharge_data_view_demographics_test AS m
  ON m.record_id = u.record_id;


-- name: load_dose_data
WITH dx AS (
  SELECT DISTINCT record_id, TRIM(diagnosis) AS substance
  FROM dose_data
  WHERE diagnosis IS NOT NULL AND TRIM(diagnosis) <> ''
)
SELECT
  dx.record_id,
  dx.substance,
  m.county,
  m.city,
  m.zip,
  m.hawaii_residency,
  m.age_group,
  m.sex,
  REPLACE(TRIM(m.race_ethnicity), 'Black of African American', 'Black or African American') AS race_ethnicity,
  m.year
FROM dx
JOIN discharge_data_view_demographics_test m ON m.record_id = dx.record_id;

-- name: load_dose_polysubstance_data
WITH dx AS (
  SELECT DISTINCT record_id, TRIM(diagnosis) AS substance
  FROM dose_data
  WHERE diagnosis IS NOT NULL AND TRIM(diagnosis) <> '' and diagnosis <> 'All Drugs'
),
poly_ids AS (
  -- polysubstance = ≥2 distinct substances
  SELECT record_id
  FROM dx
  GROUP BY record_id
  HAVING COUNT(DISTINCT substance) >= 2
)
SELECT
  dx.record_id,
  dx.substance,
  m.county,
  m.city,
  m.zip,
  m.hawaii_residency,
  m.age_group,
  m.sex,
  REPLACE(TRIM(m.race_ethnicity), 'Black of African American', 'Black or African American') AS race_ethnicity,
  m.year
FROM dx
JOIN poly_ids AS p
  ON p.record_id = dx.record_id
JOIN discharge_data_view_demographics_test m 
  ON m.record_id = dx.record_id;

-- name: load_sudors_data_view_diag_su$
WITH dx AS (
  SELECT DISTINCT incident_id, TRIM(diagnosis) AS substance
  FROM sudors_data_view_diag_su$
  WHERE diagnosis IS NOT NULL AND TRIM(diagnosis) <> ''
)
SELECT
  dx.incident_id,
  dx.substance,
  m.homeless,
  m.sex, 
  m.age_cat, 
  m.race_ethnicity,
  m.year
FROM dx
JOIN sudors_data_view_demographics$ m ON m.incident_id = dx.incident_id
WHERE m.year > 2020;  -- drop 2020 and earlier since they are partial years with different reporting rules


-- name: load_sudors_polysubstance_data
WITH
dx_union AS (
  SELECT DISTINCT incident_id, TRIM(diagnosis) AS substance
  FROM sudors_data_view_diag_su$
  WHERE diagnosis IS NOT NULL AND TRIM(diagnosis) <> ''
),
poly_ids AS (
  -- polysubstance = ≥2 distinct substances
  SELECT incident_id
  FROM dx_union
  GROUP BY incident_id
  HAVING COUNT(DISTINCT substance) >= 2
)
SELECT
  u.incident_id,
  u.substance,
  m.homeless,
  m.sex,
  m.age_cat,
  m.race_ethnicity,
  CAST(m.year AS INTEGER) AS year
FROM dx_union AS u
JOIN poly_ids AS p
  ON p.incident_id = u.incident_id
JOIN sudors_data_view_demographics$ AS m
  ON m.incident_id = u.incident_id
where m.year > 2020;  -- drop 2020 and earlier since they are partial years with different reporting rules

-- name: load_wonder_overview
SELECT
  year,
  county,
  deaths
FROM wonder_overview
WHERE year IS NOT NULL;


-- name: load_wonder_substance
SELECT
  year,
  county,
  substance,
  deaths
FROM wonder_substance
WHERE year IS NOT NULL;


-- name: load_wonder_race
SELECT
  year,
  county,
  race,
  deaths
FROM wonder_race
WHERE year IS NOT NULL;


-- name: load_wonder_age_group
SELECT
  year,
  county,
  age_group,
  deaths,
  precedence
FROM wonder_age_group
WHERE year IS NOT NULL;


-- name: load_wonder_gender
SELECT
  year,
  county,
  gender,
  deaths
FROM wonder_gender
WHERE year IS NOT NULL;


-- name: load_cares_call_volume
SELECT
    CASE 
        WHEN Line = 'NSPL Text Chat' THEN 'NSPL/988 Text'
        ELSE Line 
    END AS Line,
    Date
FROM cares_calls_inbound
WHERE Date IS NOT NULL;


-- name: load_overview_wonder_deaths
SELECT
  year,
  sum(deaths)
FROM wonder_overview
WHERE year IS NOT NULL
group by year;

-- name: load_overview_wonder_deaths_by_substance
SELECT
  year,
  substance,
  sum(deaths)
FROM wonder_substance
WHERE year IS NOT NULL
group by year, substance
order by year;

-- name: load_overview_discharges_su
SELECT
  year,
  sum(num_substance) AS total_substance
FROM discharge_data_view_test
WHERE year IS NOT NULL
and num_substance > 0
group by year
order by year;

-- name: load_overview_discharges_su_summary
SELECT DISTINCT
  REPLACE(TRIM(dx.diagnosis), 'Dissacociative', 'Dissociative') AS diagnosis,
  CAST(demo.year AS INTEGER) AS year,
  count(dx.diagnosis) as diagnosis_count
FROM discharge_data_view_diagnosis dx
INNER JOIN discharge_data_view_demographics_test demo
  ON demo.record_id = dx.record_id
WHERE dx.diagnosis IS NOT NULL
  AND TRIM(dx.diagnosis) <> ''
  and dx.diagnosis_type = 'su'
  and year IS NOT NULL
group by year, dx.diagnosis
order by year;

-- name: load_overview_discharges_su_cooccurring_summary
WITH cooccur as 
(select distinct record_id from discharge_data_view_test
 where 
	num_substance > 0
	and num_mental > 0
)
SELECT 
 REPLACE(TRIM(dx.diagnosis), 'Dissacociative', 'Dissociative') AS diagnosis,
 CAST(demo.year AS INTEGER) AS year,
 count(dx.diagnosis) AS diagnosis_count
FROM discharge_data_view_diagnosis dx
INNER JOIN cooccur co 
 ON co.record_id = dx.record_id
INNER JOIN discharge_data_view_demographics_test demo
 ON demo.record_id = dx.record_id
WHERE demo.year IS NOT NULL
group by year, dx.diagnosis
order by year;

-- name: load_discharges_su_co_sud_mh
WITH diag AS (
 SELECT DISTINCT
   record_id,
   REPLACE(TRIM(diagnosis), 'Dissacociative', 'Dissociative') AS diagnosis,
   diagnosis_type,
   is_primary
 FROM discharge_data_view_diagnosis
 WHERE diagnosis IS NOT NULL
   AND TRIM(diagnosis) <> ''
),
cooccur as 
(select distinct record_id from discharge_data_view_test
where 
	num_substance > 0
	and num_mental > 0
	and su_primary = 1 
	and mh_primary = 0)
SELECT distinct
 dx.record_id,
 dx.diagnosis,
 dx.diagnosis_type,
 dx.is_primary,
 demo.county,
 demo.city,
 demo.zip,
 demo.hawaii_residency,
 demo.age_group,
 demo.sex,
 REPLACE(TRIM(demo.race_ethnicity), 'Black of African American', 'Black or African American') AS race_ethnicity,
 CAST(demo.year AS INTEGER) AS year
FROM diag dx
INNER JOIN cooccur co 
 ON co.record_id = dx.record_id
INNER JOIN discharge_data_view_demographics_test demo
 ON demo.record_id = dx.record_id;


-- name: load_discharges_su_co_mh_sud
WITH diag AS (
 SELECT DISTINCT
   record_id,
   REPLACE(TRIM(diagnosis), 'Dissacociative', 'Dissociative') AS diagnosis,
   diagnosis_type,
   is_primary
 FROM discharge_data_view_diagnosis
 WHERE diagnosis IS NOT NULL
   AND TRIM(diagnosis) <> ''
),
cooccur as 
(select distinct record_id from discharge_data_view_test
where 
	num_substance > 0
	and num_mental > 0
	and su_primary = 0 
	and mh_primary = 1)
SELECT distinct
 dx.record_id,
 dx.diagnosis,
 dx.diagnosis_type,
 dx.is_primary,
 demo.county,
 demo.city,
 demo.zip,
 demo.hawaii_residency,
 demo.age_group,
 demo.sex,
 REPLACE(TRIM(demo.race_ethnicity), 'Black of African American', 'Black or African American') AS race_ethnicity,
 CAST(demo.year AS INTEGER) AS year
FROM diag dx
INNER JOIN cooccur co 
 ON co.record_id = dx.record_id
INNER JOIN discharge_data_view_demographics_test demo
 ON demo.record_id = dx.record_id;


-- name: load_discharges_cooccuring_su_and_mh
WITH diag AS (
 SELECT DISTINCT
   record_id,
   REPLACE(TRIM(diagnosis), 'Dissacociative', 'Dissociative') AS diagnosis,
   diagnosis_type
 FROM discharge_data_view_diagnosis
 WHERE diagnosis IS NOT NULL
   AND TRIM(diagnosis) <> ''
),
cooccur as 
(select distinct record_id from discharge_data_view_test
where 
	num_substance > 0
	and num_mental > 0
  and (su_primary = 1 
	or mh_primary = 1))
SELECT distinct
 dx.record_id,
 dx.diagnosis,
 dx.diagnosis_type,
 demo.county,
 demo.city,
 demo.zip,
 demo.hawaii_residency,
 demo.age_group,
 demo.sex,
 REPLACE(TRIM(demo.race_ethnicity), 'Black of African American', 'Black or African American') AS race_ethnicity,
 CAST(demo.year AS INTEGER) AS year
FROM diag dx
INNER JOIN cooccur co 
 ON co.record_id = dx.record_id
INNER JOIN discharge_data_view_demographics_test demo
 ON demo.record_id = dx.record_id;

-- name: load_crisis_mobile_outreach
SELECT 
  ReferralTo as referral_destination, 
  cnt, 
  Percent as pct
FROM BH808_CMO_Referral_Destinations
where pct >= 1;

-- name: load_crisis_mobile_outreach_last_updated
SELECT CAST(MAX(DispatchDate) AS date) AS last_updated
FROM dbo.AMHD_Crisis_Mobile_Outreach;


-- name: load_crisis_mobile_outreach_last_updated_sqlite
SELECT date(MAX(DispatchDate)) AS last_updated
FROM AMHD_Crisis_Mobile_Outreach;


-- name: crisis-bed-occupancy
SELECT 
    FORMAT(DispatchDate, 'yyyy-MM') AS dispatch_month, 
    program_county_value, 
    COUNT(DISTINCT PATID) AS bed_ct 
FROM AMHD_Crisis_Mobile_Outreach 
WHERE CMOReferralTo_Value = 'LCRS' 
  AND DispatchDate >= DATEADD(month, -12, CAST(GETDATE() AS DATE)) 
GROUP BY 
    FORMAT(DispatchDate, 'yyyy-MM'), 
    program_county_value 
ORDER BY 
    dispatch_month ASC, 
    program_county_value ASC;


-- name: load_adad_clients_served
SELECT
  client_id,
  county,
  modality,
  [date] AS service_date
FROM adad_service_view_test
WHERE [date] IS NOT NULL;

-- name: load_adad_kpi_total
SELECT COUNT(DISTINCT client_id) AS client_count
FROM adad_service_view_test;


-- name: load_adad_cooccurring
select 
  sv.client_id, 
  sv.county, 
  sv.modality, 
  sv.date, 
  iv.num_su, 
  iv.num_mh,  
  iv.su_primary, 
  iv.mh_primary
from adad_service_view_test as sv
inner join adad_indicators_view iv 
on 
  sv.client_id = iv.client_id
  and iv.num_mh >= 1
  and iv.num_su >= 1;

-- name: load_amhd_year_all
select * from amhd_aggregate_reporting where date_type = 'Year' and service_category = 'All' order by date;
-- name: load_amhd_month_all
select * from amhd_aggregate_reporting where date_type = 'Month' and service_category = 'All' order by date;
-- name: load_amhd_day_all
select * from amhd_aggregate_reporting where date_type = 'Day' and service_category = 'All' order by date;
-- name: load_amhd_year_categories
select * from amhd_aggregate_reporting where date_type = 'Year' and service_category <> 'All' order by date;
-- name: load_amhd_month_categories
select * from amhd_aggregate_reporting where date_type = 'Month' and service_category <> 'All' order by date;
-- name: load_amhd_day_categories
select * from amhd_aggregate_reporting where date_type = 'Day' and service_category <> 'All' order by date;
-- name: load_amhd_kpi_total
select * from amhd_aggregate_reporting where date_type = 'All';

-- name: load_amhd_cooccurring_year_all
select * from amhd_cooccurring_aggregate_reporting where date_type = 'Year' and service_category = 'All' order by date;
-- name: load_amhd_cooccurring_month_all
select * from amhd_cooccurring_aggregate_reporting where date_type = 'Month' and service_category = 'All' order by date;
-- name: load_amhd_cooccurring_day_all
select * from amhd_cooccurring_aggregate_reporting where date_type = 'Day' and service_category = 'All' order by date;
-- name: load_amhd_cooccurring_year_categories
select * from amhd_cooccurring_aggregate_reporting where date_type = 'Year' and service_category <> 'All' order by date;
-- name: load_amhd_cooccurring_month_categories
select * from amhd_cooccurring_aggregate_reporting where date_type = 'Month' and service_category <> 'All' order by date;
-- name: load_amhd_cooccurring_day_categories
select * from amhd_cooccurring_aggregate_reporting where date_type = 'Day' and service_category <> 'All' order by date;
-- name: load_amhd_cooccurring_kpi_total
select * from amhd_cooccurring_aggregate_reporting where date_type = 'All';


-- name: load_camhd_clients_served
SELECT
  client_id,
  [date] AS service_date
FROM camhd_service_view_test
WHERE [date] IS NOT NULL;

-- name: load_camhd_cooccurring
SELECT
  client_id,
  date AS service_date
FROM camhd_co_mh_su_view
WHERE date IS NOT NULL;


-- name: load_lcrf_occupancy
select 
  Date, 
  Facility, 
  Occupancy_Rate 
from BH808_Crisis_Bed_Occupancy_LCRS_view;


-- name: load_sicm_occupancy
select 
  Date, 
  Facility, 
  Occupancy_Rate 
from BH808_Crisis_Bed_Occupancy_SICM_view;


-- name: load_cares_calls_by_nature_top_10
select TOP 10
	CallNature as Nature_of_Call,
	(proportion * 100) as percentage_of_total
from BH808_Overview_Call_Nature 
order by percentage_of_total desc;

-- name: load_cares_calls_by_nature_top_10_sqlite
select 
	CallNature as Nature_of_Call,
	(proportion * 100) as percentage_of_total
from BH808_Overview_Call_Nature 
order by percentage_of_total desc
LIMIT 10;


-- name: load_cares_calls_last_updated
SELECT CAST(MAX(Date) AS date) AS last_updated
FROM dbo.cares_calls_inbound;


-- name: load_cares_calls_last_updated_sqlite
SELECT date(MAX(Date)) AS last_updated
FROM cares_calls_inbound;



-- name: load_cares_calls_by_line_6_months
SELECT 
  date, 
  line, 
  num_calls 
FROM BH808_Overview_Crisis_Volume_View;


-- name: load_cares_statistics_top_box
Select 
  CallVolume, 
  CallAnswer, 
  CallSpeed, 
  CallStab, 
  ChatVol, 
  ChatAnswer, 
  ChatSpeed, 
  ChatStab, 
  TextVol, 
  TextAnswer, 
  TextSpeed,
  TextStab 
from BH808_Overview_Top_Box;



-- name: load_crisis_mobile_outreach_6_months
SELECT 
	Month_Year as Date,
	Approved_visits as num_calls
FROM BH808_Overview_CMO_Dispatches
Order by Date;

-- name: load_overview_discharges_su_with_substance
WITH dx AS (
  SELECT DISTINCT 
    record_id, 
    REPLACE(TRIM(diagnosis), 'Dissacociative', 'Dissociative') AS substance
  FROM discharge_data_view_diag_su
  WHERE diagnosis IS NOT NULL AND TRIM(diagnosis) <> ''
)
SELECT
  CAST(m.year AS INTEGER) AS year,
  dx.substance,
  COUNT(DISTINCT dx.record_id) AS num_substance
FROM dx
JOIN discharge_data_view_demographics_test m ON m.record_id = dx.record_id
WHERE m.year IS NOT NULL
GROUP BY m.year, dx.substance
ORDER BY m.year, dx.substance;
