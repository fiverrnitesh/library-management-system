const toggle = document.getElementById("nav-toggle");
const sidebar = document.getElementById("sidebar");
if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
        sidebar.classList.toggle("open");
    });
}

document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
        const message = form.getAttribute("data-confirm") || "Are you sure?";
        if (!window.confirm(message)) {
            event.preventDefault();
        }
    });
});

function daysLate(due, returned) {
    const dueDate = new Date(due + "T00:00:00");
    const returnDate = new Date(returned + "T00:00:00");
    const diff = Math.round((returnDate - dueDate) / 86400000);
    return diff > 0 ? diff : 0;
}

function updateFinePreview(input) {
    const target = document.getElementById(input.getAttribute("data-fine-preview"));
    if (!target) {
        return;
    }
    const rate = Number(document.body.getAttribute("data-fine-per-day") || "0");
    const amount = daysLate(input.getAttribute("data-due"), input.value) * rate;
    target.textContent = "₹" + amount.toFixed(2);
}

document.querySelectorAll("[data-fine-preview]").forEach(function (input) {
    updateFinePreview(input);
    input.addEventListener("change", function () {
        updateFinePreview(input);
    });
});
