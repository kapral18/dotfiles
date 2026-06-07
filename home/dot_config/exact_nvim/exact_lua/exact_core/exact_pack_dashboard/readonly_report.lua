-- Facade over the report submodules. Callers require
-- `core.pack_dashboard.report` and use the names re-exported here; the concrete
-- logic lives in the cohesive submodules under `report/`:
--   notify - user-facing check progress/result notifications
--   parser - `nvim-pack://confirm` report buffer -> cache parsing
--   fetch  - concurrent `git fetch` of plugin remotes
--   rows   - cache scan/purge/ensure and dashboard row assembly
local notify = require("core.pack_dashboard.report.notify")
local parser = require("core.pack_dashboard.report.parser")
local fetch = require("core.pack_dashboard.report.fetch")
local pipeline = require("core.pack_dashboard.report.pipeline")
local rows = require("core.pack_dashboard.report.rows")

local M = {}

M.notify_err = notify.notify_err
M.refresh_pack_report_cache_from_report_buffer = parser.refresh_pack_report_cache_from_report_buffer
M.fetch_pack_remotes_async = fetch.fetch_pack_remotes_async
M.run_refresh_pipeline = pipeline.run
M.scan_updates_to_cache = rows.scan_updates_to_cache
M.ensure_dashboard_cache = rows.ensure_dashboard_cache
M.collect_dashboard_rows = rows.collect_dashboard_rows
M.collect_dashboard_row = rows.collect_dashboard_row

return M
