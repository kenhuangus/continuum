# Capture Alibaba Cloud Workbench / ECS console screenshot

Save the screenshot as `docs/screenshots/alibaba_workbench.png` (create the file after you capture it; do not invent or fabricate an image).

Use the **Alibaba Cloud International** site only.

## Click path

1. Open [https://www.alibabacloud.com/](https://www.alibabacloud.com/) and sign in to your International account.
2. Open the ECS console (from the product menu: **Elastic Compute Service**, or via the International console home).
3. Confirm the region matches where you launched Continuum (for example Singapore / `ap-southeast-1`).
4. Go to **Instances** → **Instances**.
5. Select your Continuum ECS instance in the list.
6. Capture one of the following so the screenshot shows a live Running instance (not a fabricated URL or IP):
   - Instance details page with **Status: Running**, or
   - **Workbench** / remote connection entry (connect via Workbench if available for the instance).
7. Take a screenshot of that console view (OS screenshot tool is fine).
8. Save it to the repo path:

   `docs/screenshots/alibaba_workbench.png`

## Do not

- Invent a `PUBLIC_URL` or fake instance public IP in docs or filenames.
- Commit placeholder or generated fake PNGs.
- Use the China-site console if the PoD expects International.
