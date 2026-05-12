# Walkthrough GIF Recording Steps

These steps describe how to regenerate each animated GIF walkthrough for Seizu.
All recordings use the `mcp__claude-in-chrome__*` browser automation tools.

## General notes

- Use `tabs_create_mcp` to open a fresh tab before each recording.
- Do **not** navigate directly to `/app/reports/<id>` — it redirects to the dashboard.
  Instead, navigate to `/` first (or the dashboard), then click the report name in the sidebar.
- Use `javascript_tool` (JS `window.scrollBy`) for large scrolls to avoid consuming GIF frames.
  Only `computer` and `navigate` tool calls count toward the 50-frame cap.
- Export settings: `quality: 6`, `showClickIndicators: true`, all other overlays `false`.
- The browser viewport renders at 1920×890 with a ~1.224 DPR.
  DOM coordinates × (1/1.224) ≈ screenshot coordinates.

---

## GIF 1: Query Console (`seizu-query-console-walkthrough.gif`)

**Starting URL:** `http://localhost:8080/app/query-console`
(Navigate to dashboard first, then click "Query Console" in the sidebar.)

1. Start recording. Take an initial screenshot.
2. Wait for the schema panel on the left to finish loading.
3. Scroll the schema panel down to **CVEMetadata** and click it to expand it.
4. Hover over the **GitHubDependabotAlert** node entry for ~2 s to show its tooltip.
5. Click **GitHubDependabotAlert** — this runs a discovery query and populates the graph.
6. Scroll the node detail panel on the right to show its properties.
7. Click the **Table** tab above the graph.
8. Click the **Raw** tab.
9. Open the query history panel.
10. Click the history entry:
    `MATCH path = (n:\`Dependency\`)-[r]-(m) RETURN path LIMIT 25`
    to load it into the editor.
11. Take a final screenshot. Stop recording.
12. Export as `seizu-query-console-walkthrough.gif`.

---

## GIF 2: Report Viewing (`seizu-report-walkthrough.gif`)

**Starting URL:** `http://localhost:8080/app/reports/7458123696264187904?panel_examples_search=CVE-2024`
(Navigate to dashboard, click "Panel Examples" in the sidebar.)

1. Start recording. Take an initial screenshot showing the report with CVE-2024 pre-filled.
2. Click the chevron on the **"About this report"** panel to collapse it.
3. Scroll down to the pie charts section.
4. Hover over the **HIGH** arc label on the severity pie chart for ~2 s.
5. Scroll down to the graph panel. Click a severity node to highlight its connections.
6. Scroll back to the top. Change the **CVE ID Search** input to `CVE-2026` and wait for data to refresh.
7. Open the **Base Severity** autocomplete and select **CRITICAL**. Wait for refresh.
8. Scroll to the bottom of the report.
9. Take a final screenshot. Stop recording.
10. Export as `seizu-report-walkthrough.gif`.

---

## GIF 4: MCP Toolsets & Skillsets (`seizu-toolsets-skillsets-walkthrough.gif`)

**Starting URL:** `http://localhost:8080/app/toolsets`
(Navigate to dashboard, click "MCP Toolsets" in the sidebar.)

1. Start recording. Take an initial screenshot of the dashboard.
2. Click **MCP Toolsets** in the sidebar — navigates to the toolsets list.
3. Hover over **GitHub Security** for ~2 s, then click it to enter its tools list.
4. Click **org_overview** to open the detail modal.
5. Scroll the modal to the bottom (JS scroll or mouse wheel).
6. Wait ~2 s, then click **✕** to close the modal.
7. Click the **⋮ More actions** button on the `org_overview` row → **Edit**.
8. Scroll the Edit Tool dialog to the bottom.
9. Wait ~2 s, then click **CANCEL**.
10. Click **MCP Skillsets** in the sidebar — navigates to the skillsets list.
11. Hover over **GitHub Security Investigations** for ~2 s, then click it to enter its skills list.
12. Hover over **GitHub Organization Security Overvi...** for ~2 s, then click it to open the detail modal.
13. Scroll the modal to the bottom.
14. Wait ~2 s, then click **CLOSE**.
15. Click **⋮ More actions** on the skill row → **Render**.
16. Type `mappedsky` in the **org** field, then click **RENDER**.
17. Scroll the rendered output to the end.
18. Wait ~2 s, then click **CLOSE**.
19. Click **⋮ More actions** → **Edit**.
20. Scroll the Edit Skill dialog to the bottom.
21. Click **CANCEL**. Take a final screenshot. Stop recording.
22. Export as `seizu-toolsets-skillsets-walkthrough.gif`.

---

## GIF 3: Edit Report (`seizu-edit-report-walkthrough.gif`)

**Starting URL:** `http://localhost:8080/app/reports/7458123696264187904?panel_examples_search=CVE-2024`
(Navigate to dashboard, click "Panel Examples" in the sidebar.)

### Pre-flight: restore a clean version

Before recording, check the version history at
`/app/reports/7458123696264187904/history`.
If a recording-created version (e.g. v3 by "Seizu Admin") is current,
restore the previous seed version (e.g. v2 "Updated from YAML dashboard config")
via its three-dot menu → **Restore**, then navigate back to the report.

### Recording steps

1. Start recording. Take an initial screenshot of the report view.
2. Click **EDIT REPORT** (top-right).
3. Wait ~2 s for the edit view to load (Named Queries section is expanded by default).
4. Click the chevron on **Named Queries** to collapse it.
5. Click the **pencil (edit) icon** on the **CVE ID Search** input row to open the Edit Input dialog.
6. Wait ~3 s to let the viewer see the dialog, then click **CANCEL**.
7. Scroll down (JS scroll) until the **About this report** markdown panel's action buttons
   (pencil, trash, move, resize) are visible at the bottom right of the panel.
8. Click the **pencil (Edit panel) icon** for the markdown panel.
9. In the Edit Panel dialog, click the **MARKDOWN** tab.
10. Click inside the markdown textarea and press `Ctrl+End` to move to the end.
    (Use JS `textarea.selectionStart = textarea.value.length` if the key does not scroll
    the textarea itself.)
11. Type a new line:
    ```
    Markdown supports basic templating, using Markdoc: input example {% $panel_examples_severity %}
    ```
    Verify there is a space after `Markdoc:` — use `document.execCommand('insertText')` to
    fix a missing space if the typing glitch recurs.
12. Click **SAVE PANEL**.
13. JS-scroll down to the **Table with text input filter** row. The panel inside it is
    "CVEs matching CVE ID...".
14. Drag the **resize handle** (diagonal-arrow icon, bottom-right corner of the panel)
    leftward to resize from 12 columns to 6.
    - Handle DOM position: `document.querySelector('.react-resizable-handle')` — use the one
      whose `getBoundingClientRect().top` matches the current panel bottom.
    - Drag from the handle's x to approximately `panel_left + (full_width / 2)`.
15. JS-scroll down to the **Table with autocomplete filter** row. The panel inside it is
    "CVEs by severity".
16. Drag its resize handle the same way to resize to 6 columns.
17. Click the **Move to row** icon (crosshair button) on the "CVEs by severity" panel.
    In the dropdown, select **Table with text input filter**.
18. JS-scroll up to the **Table with text input filter** row name input.
    Triple-click it and type `Tables with inputs`.
19. JS-scroll to the now-empty **Table with autocomplete filter** row.
    Click its red **delete row** button (far right of the row header).
20. Click **SAVE VERSION** (top-right, fixed toolbar).
21. Take a final screenshot of the saved report view. Stop recording.
22. Export as `seizu-edit-report-walkthrough.gif`.
