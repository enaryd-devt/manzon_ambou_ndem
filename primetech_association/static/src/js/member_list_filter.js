/** @odoo-module **/

const SEARCH_INPUT_SELECTOR = ".pt-member-list-search";
const SCOPE_SELECTOR = ".pt-member-filter-scope";
const ROW_SELECTOR = ".o_list_table tbody tr.o_data_row";

function normalize(value) {
    return (value || "")
        .toString()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
}

function filterScope(input) {
    const scope = input.closest(SCOPE_SELECTOR);

    if (!scope) {
        return;
    }

    const query = normalize(input.value);
    const rows = scope.querySelectorAll(ROW_SELECTOR);

    for (const row of rows) {
        const matches = !query || normalize(row.textContent).includes(query);
        row.classList.toggle("pt-member-filter-hidden", !matches);
    }
}

function filterAllActiveScopes() {
    document.querySelectorAll(SEARCH_INPUT_SELECTOR).forEach((input) => {
        filterScope(input);
    });
}

document.addEventListener("input", (event) => {
    if (!(event.target instanceof Element)) {
        return;
    }

    const input = event.target.closest(SEARCH_INPUT_SELECTOR);

    if (input) {
        filterScope(input);
    }
});

let refreshScheduled = false;

function scheduleRefresh() {
    if (refreshScheduled) {
        return;
    }

    refreshScheduled = true;

    window.requestAnimationFrame(() => {
        refreshScheduled = false;
        filterAllActiveScopes();
    });
}

function startMemberListFilter() {
    filterAllActiveScopes();

    new MutationObserver(scheduleRefresh).observe(document.body, {
        childList: true,
        subtree: true,
    });
}

if (document.body) {
    startMemberListFilter();
} else {
    document.addEventListener("DOMContentLoaded", startMemberListFilter, {
        once: true,
    });
}
