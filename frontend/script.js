
const API_BASE = "http://127.0.0.1:8000";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

let jobs = [];
let recipientRowCount = 0;

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;",
        '"': "&quot;", "'": "&#39;"
    })[char]);
}

function showMessage(element, message, type = "success") {
    element.className = `message ${type}`;
    element.textContent = message;
}

function clearMessage(element) {
    element.className = "message hidden";
    element.textContent = "";
}


function setPage(pageName) {
    const names = {
        dashboard: "Dashboard",
        create: "Create certificates",
        studio: "Template Studio",
        jobs: "Generation history"
    };

    if (!names[pageName]) {
        pageName = "dashboard";
    }

    Object.keys(names).forEach(name => {
        const page = document.querySelector(`#${name}-page`);

        if (page) {
            page.classList.toggle("hidden", name !== pageName);
        }
    });

    document.querySelectorAll(".nav-item").forEach(item => {
        item.classList.toggle("active", item.dataset.page === pageName);
    });

    const breadcrumb = document.querySelector("#breadcrumb-page");

    if (breadcrumb) {
        breadcrumb.textContent = names[pageName];
    }

    if (pageName === "dashboard") loadDashboard();
    if (pageName === "jobs") loadJobs();
}


$$(".nav-item").forEach(item => {
    item.addEventListener("click", event => {
        event.preventDefault();
        setPage(item.dataset.page);
    });
});

$$("[data-go]").forEach(button => {
    button.addEventListener("click", () => setPage(button.dataset.go));
});

function addRecipientRow(name = "", email = "") {
    recipientRowCount++;
    const row = document.createElement("tr");
    row.innerHTML = `
        <td>${$("#recipient-rows").children.length + 1}</td>
        <td><input class="recipient-name" type="text" maxlength="200"
            placeholder="Recipient full name" aria-label="Recipient name"
            value="${escapeHTML(name)}"></td>
        <td><input class="recipient-email" type="email" maxlength="254"
            placeholder="name@example.com" aria-label="Recipient email"
            value="${escapeHTML(email)}"></td>
        <td><button type="button" class="remove-row" aria-label="Remove recipient">×</button></td>
    `;

    row.querySelector(".remove-row").addEventListener("click", () => {
        if ($("#recipient-rows").children.length <= 1) {
            alert("Add at least one recipient to generate certificates.");
            return;
        }
        row.remove();
        updateRecipientRows();
    });

    $("#recipient-rows").appendChild(row);
    updateRecipientRows();
}

function updateRecipientRows() {
    $$("#recipient-rows tr").forEach((row, index) => {
        row.children[0].textContent = index + 1;
    });
    const count = $("#recipient-rows").children.length;
    $("#recipient-count").textContent = `${count} recipient${count === 1 ? "" : "s"}`;
}

$("#add-recipient").addEventListener("click", () => addRecipientRow());

function collectRecipients() {
    return $$("#recipient-rows tr").map(row => ({
        name: row.querySelector(".recipient-name").value.trim(),
        email: row.querySelector(".recipient-email").value.trim()
    }));
}

function validateForm(eventName, recipients) {
    if (!eventName) return "Enter an event or program name.";
    if (!recipients.length) return "Add at least one recipient.";

    for (let i = 0; i < recipients.length; i++) {
        const recipient = recipients[i];

        if (!recipient.name) return `Enter a name for recipient ${i + 1}.`;
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipient.email)) {
            return `Enter a valid email address for recipient ${i + 1}.`;
        }
    }
    return "";
}

$("#generate-button").addEventListener("click", async () => {
    const eventName = $("#event-name").value.trim();
    const recipients = collectRecipients();
    const error = validateForm(eventName, recipients);
    const message = $("#create-message");

    clearMessage(message);

    if (error) {
        showMessage(message, error, "error");
        return;
    }

    const button = $("#generate-button");
    button.disabled = true;
    button.textContent = "Generating certificates…";

    try {
        const response = await fetch(`${API_BASE}/api/jobs/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ event_name: eventName, recipients })
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            const detail = Array.isArray(data.detail)
                ? data.detail.map(item => item.msg).join(", ")
                : data.detail;
            throw new Error(detail || `Request failed (${response.status})`);
        }

        const jobId = data.job_id ?? data.id;
        showMessage(
            message,
            `Job created successfully. Job ID: ${jobId ?? "created"}. ` +
            `Successful: ${data.successful_count ?? 0}. Failed: ${data.failed_count ?? 0}.`,
            "success"
        );

        $("#event-name").value = "";
        $("#recipient-rows").innerHTML = "";
        addRecipientRow();

        await loadDashboard();
        setTimeout(() => setPage("jobs"), 900);
    } catch (error) {
        showMessage(
            message,
            `${error.message}. Confirm that FastAPI is running and the API response matches the frontend.`,
            "error"
        );
    } finally {
        button.disabled = false;
        button.textContent = "Generate certificates →";
    }
});

async function apiGet(path) {
    const response = await fetch(`${API_BASE}${path}`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.detail || `Request failed (${response.status})`);
    }
    return data;
}

async function fetchJob(jobId) {
    return apiGet(`/api/jobs/${encodeURIComponent(jobId)}/`);
}

async function loadJobs() {
    const tbody = $("#all-jobs");
    tbody.innerHTML =
        '<tr><td colspan="7" class="empty-state">Loading jobs...</td></tr>';
    clearMessage($("#jobs-message"));

    try {
        const data = await apiGet("/api/jobs/");

        jobs = Array.isArray(data) ? data : [];

        if (jobs.length === 0) {
            tbody.innerHTML =
                '<tr><td colspan="7" class="empty-state">No jobs found. Create your first batch.</td></tr>';
            return;
        }

        tbody.innerHTML = jobs
            .map(job => renderJobRow(job, true))
            .join("");

    } catch (error) {
        tbody.innerHTML =
            '<tr><td colspan="7" class="empty-state">Unable to load jobs.</td></tr>';

        showMessage(
            $("#jobs-message"),
            `Could not load generation history: ${error.message}`,
            "error"
        );
    }
}


function renderJobRow(job, includeDetails = false) {
    const jobId = job.job_id ?? job.id ?? "—";
    const eventName = job.event_name ?? "Certificate batch";
    const total = job.total_recipients ?? job.total ?? 0;
    const successful = job.successful_count ?? job.successful ?? 0;
    const failed = job.failed_count ?? job.failed ?? 0;
    const status = String(job.status ?? "UNKNOWN").toLowerCase();

    const download = successful > 0
        ? `<button class="table-action" data-download="${escapeHTML(jobId)}">Download ZIP</button>`
        : "—";

    return `<tr>
        <td class="job-id">${escapeHTML(jobId)}</td>
        <td class="event-name">${escapeHTML(eventName)}</td>
        ${includeDetails ? `<td>${total}</td><td>${successful}</td><td>${failed}</td>` : `<td>${total}</td>`}
        <td><span class="status-badge ${escapeHTML(status)}">${escapeHTML(job.status ?? "UNKNOWN")}</span></td>
        <td>${download}</td>
    </tr>`;
}


async function loadDashboard() {
    try {
        const data = await apiGet("/api/jobs/");
        jobs = Array.isArray(data) ? data : [];

        $("#total-jobs").textContent = jobs.length;

        $("#total-recipients").textContent = jobs.reduce(
            (sum, job) => sum + Number(job.total_recipients || 0),
            0
        );

        $("#successful-count").textContent = jobs.reduce(
            (sum, job) => sum + Number(job.successful_count || 0),
            0
        );

        $("#failed-count").textContent = jobs.reduce(
            (sum, job) => sum + Number(job.failed_count || 0),
            0
        );

        $("#recent-jobs").innerHTML = jobs.length
            ? jobs.slice(0, 5).map(job => renderJobRow(job)).join("")
            : '<tr><td colspan="5" class="empty-state">Create your first certificate batch to see it here.</td></tr>';

    } catch (error) {
        console.error("Dashboard loading failed:", error);
        $("#recent-jobs").innerHTML =
            '<tr><td colspan="5" class="empty-state">Unable to load recent jobs.</td></tr>';
    }
}

async function downloadZip(jobId) {
    try {
        const response = await fetch(
            `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/certificates/`
        );
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || "ZIP download failed");
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `job_${jobId}_certificates.zip`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
    } catch (error) {
        alert(`Could not download certificates: ${error.message}`);
    }
}

document.addEventListener("click", event => {
    const button = event.target.closest("[data-download]");
    if (button) downloadZip(button.dataset.download);
});

$("#refresh-jobs").addEventListener("click", loadJobs);

async function checkApi() {
    try {
        await apiGet("/");
        $("#connection-status").textContent = "API connected";
        $(".status-dot").classList.add("online");
    } catch {
        $("#connection-status").textContent = "API offline";
        $(".status-dot").classList.remove("online");
    }
}


let certificateCanvas = null;
let selectedTextObject = null;

function initializeCertificateEditor(imageUrl) {
    if (typeof fabric === "undefined") {
        alert("The editor library could not load. Check your internet connection.");
        return;
    }

    const preview = document.querySelector("#template-preview");
    const emptyState = document.querySelector("#template-empty-state");
    const canvasElement = document.querySelector("#certificate-canvas");

    const image = new Image();

    image.onload = () => {
        const maxWidth = Math.max(300, preview.clientWidth - 24);
        const maxHeight = 420;
        const scale = Math.min(
            maxWidth / image.naturalWidth,
            maxHeight / image.naturalHeight,
            1
        );

        const width = Math.round(image.naturalWidth * scale);
        const height = Math.round(image.naturalHeight * scale);

        if (certificateCanvas) {
            certificateCanvas.dispose();
        }

        canvasElement.hidden = false;
        emptyState.hidden = true;

        certificateCanvas = new fabric.Canvas("certificate-canvas", {
            width,
            height,
            preserveObjectStacking: true,
            selection: true
        });

        certificateCanvas.setDimensions({ width, height });

        fabric.Image.fromURL(imageUrl, (backgroundImage) => {
            backgroundImage.scaleToWidth(width);
            backgroundImage.scaleToHeight(height);

            certificateCanvas.setBackgroundImage(
                backgroundImage,
                certificateCanvas.renderAll.bind(certificateCanvas)
            );
        });

        certificateCanvas.on("selection:created", updateSelectedText);
        certificateCanvas.on("selection:updated", updateSelectedText);
        certificateCanvas.on("selection:cleared", () => {
            selectedTextObject = null;
        });
    };

    image.onerror = () => alert("Unable to load this certificate image.");
    image.src = imageUrl;
}

function updateSelectedText() {
    const active = certificateCanvas?.getActiveObject();

    if (active && active.type === "textbox") {
        selectedTextObject = active;
        document.querySelector("#text-content").value = active.text;
        document.querySelector("#font-family").value = active.fontFamily;
        document.querySelector("#font-size").value = active.fontSize;
        document.querySelector("#font-size-value").textContent =
            `${active.fontSize} px`;
        document.querySelector("#font-color").value = active.fill;
    }
}

const templateInput = document.querySelector("#template-image");

templateInput?.addEventListener("change", () => {
    const file = templateInput.files[0];
    if (!file) return;

    if (!["image/png", "image/jpeg"].includes(file.type)) {
        alert("Please choose a PNG or JPG image.");
        templateInput.value = "";
        return;
    }

    const imageUrl = URL.createObjectURL(file);

    document.querySelector("#template-file-name").textContent = file.name;

    initializeCertificateEditor(imageUrl);
});

document.querySelector("#add-text-button")?.addEventListener("click", () => {
    if (!certificateCanvas) {
        alert("Upload a certificate image first.");
        return;
    }

    const text = new fabric.Textbox(
        document.querySelector("#text-content").value || "Recipient Name",
        {
            left: certificateCanvas.width / 2,
            top: certificateCanvas.height / 2,
            originX: "center",
            originY: "center",
            fontFamily: document.querySelector("#font-family").value,
            fontSize: Number(document.querySelector("#font-size").value),
            fill: document.querySelector("#font-color").value,
            textAlign: "center",
            width: certificateCanvas.width * 0.7,
            editable: true
        }
    );

    certificateCanvas.add(text);
    certificateCanvas.setActiveObject(text);
    selectedTextObject = text;
    certificateCanvas.renderAll();
});

document.querySelector("#text-content")?.addEventListener("input", event => {
    if (!selectedTextObject) return;
    selectedTextObject.set("text", event.target.value);
    certificateCanvas.requestRenderAll();
});

document.querySelector("#font-family")?.addEventListener("change", event => {
    if (!selectedTextObject) return;
    selectedTextObject.set("fontFamily", event.target.value);
    certificateCanvas.requestRenderAll();
});

document.querySelector("#font-size")?.addEventListener("input", event => {
    const size = Number(event.target.value);
    document.querySelector("#font-size-value").textContent = `${size} px`;

    if (!selectedTextObject) return;
    selectedTextObject.set("fontSize", size);
    certificateCanvas.requestRenderAll();
});

document.querySelector("#font-color")?.addEventListener("input", event => {
    if (!selectedTextObject) return;
    selectedTextObject.set("fill", event.target.value);
    certificateCanvas.requestRenderAll();
});

document.querySelector("#delete-text-button")?.addEventListener("click", () => {
    if (!certificateCanvas || !selectedTextObject) return;

    certificateCanvas.remove(selectedTextObject);
    certificateCanvas.discardActiveObject();
    selectedTextObject = null;
    certificateCanvas.requestRenderAll();
});

addRecipientRow();
checkApi();
loadDashboard();
