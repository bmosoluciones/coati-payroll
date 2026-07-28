// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.

// Note: The following variables are initialized in the HTML template with Jinja2:
// - schema: initialized from {{ schema_data|tojson }}
// - exampleSchema: initialized from {{ example_schema_data|tojson }}
// - availableSources: initialized from {{ available_sources_data|tojson }}

// Counter for unique IDs
let inputCounter = 0;
let stepCounter = 0;
let tableCounter = 0;

// Sortable instances
let inputsSortable = null;
let stepsSortable = null;

function initializeSortable() {
    // Initialize sortable for inputs
    const inputsContainer = document.getElementById('inputs-container');
    if (inputsContainer && typeof Sortable !== 'undefined') {
        inputsSortable = Sortable.create(inputsContainer, {
            animation: 150,
            handle: '.drag-handle',
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
            onEnd: function() {
                updateJsonPreview();
            }
        });
    }

    // Initialize sortable for steps
    const stepsContainer = document.getElementById('steps-container');
    if (stepsContainer && typeof Sortable !== 'undefined') {
        stepsSortable = Sortable.create(stepsContainer, {
            animation: 150,
            handle: '.drag-handle',
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
            onEnd: function() {
                updateJsonPreview();
            }
        });
    }
}

function loadSchemaToEditor() {
    // Load meta
    if (schema.meta) {
        document.getElementById('meta-name').value = schema.meta.name || '';
        document.getElementById('meta-reference-currency').value = schema.meta.reference_currency || schema.meta.currency || '';
        document.getElementById('meta-description').value = schema.meta.description || '';
    }

    // Load inputs
    const inputsContainer = document.getElementById('inputs-container');
    inputsContainer.innerHTML = '';
    if (schema.inputs && schema.inputs.length > 0) {
        schema.inputs.forEach(input => addInput(input));
    }

    // Load steps
    const stepsContainer = document.getElementById('steps-container');
    stepsContainer.innerHTML = '';
    if (schema.steps && schema.steps.length > 0) {
        schema.steps.forEach(step => addStep(step.type, step));
    }

    // Load tax tables
    const tablesContainer = document.getElementById('tax-tables-container');
    tablesContainer.innerHTML = '';
    if (schema.tax_tables) {
        Object.entries(schema.tax_tables).forEach(([name, brackets]) => {
            addTaxTable(name, brackets);
        });
    }

    // Load output
    updateOutputSelect();
    document.getElementById('output-variable').value = schema.output || '';
}

function addInput(data = null) {
    const container = document.getElementById('inputs-container');
    const id = inputCounter++;

    // Build source options grouped by category
    let sourceOptionsHtml = '<option value="">Select source or enter value...</option>';
    let currentCategory = '';
    availableSources.forEach(source => {
        if (source.category !== currentCategory) {
            if (currentCategory !== '') {
                sourceOptionsHtml += '</optgroup>';
            }
            sourceOptionsHtml += `<optgroup label="${source.category}">`;
            currentCategory = source.category;
        }
        sourceOptionsHtml += `<option value="${source.value}" title="${source.description}">${source.label}</option>`;
    });
    if (currentCategory !== '') {
        sourceOptionsHtml += '</optgroup>';
    }

    const currentSourceValue = data?.source || data?.default || '';

    const html = `
        <div class="input-item" id="input-${id}">
            <div class="drag-handle">
                <i class="bi bi-grip-vertical"></i>
            </div>
            <div class="reorder-buttons">
                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="moveInputUp(${id})" title="Move up">
                    <i class="bi bi-arrow-up"></i>
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="moveInputDown(${id})" title="Move down">
                    <i class="bi bi-arrow-down"></i>
                </button>
            </div>
            <button type="button" class="btn btn-danger btn-sm remove-btn" onclick="removeInput(${id})">
                <i class="bi bi-x"></i>
            </button>
            <div class="row">
                <div class="col-md-4">
                    <label class="form-label small">Name</label>
                    <input type="text" class="form-control form-control-sm input-name"
                           value="${data?.name || ''}" placeholder="Ex: salary_monthly"
                           onchange="updateJsonPreview()">
                </div>
                <div class="col-md-3">
                    <label class="form-label small">Type</label>
                    <select class="form-select form-select-sm input-type" onchange="updateJsonPreview()">
                        <option value="decimal" ${data?.type === 'decimal' ? 'selected' : ''}>Decimal</option>
                        <option value="integer" ${data?.type === 'integer' ? 'selected' : ''}>Integer</option>
                        <option value="string" ${data?.type === 'string' ? 'selected' : ''}>Text</option>
                        <option value="boolean" ${data?.type === 'boolean' ? 'selected' : ''}>Boolean</option>
                        <option value="date" ${data?.type === 'date' ? 'selected' : ''}>Date</option>
                    </select>
                </div>
                <div class="col-md-5">
                    <label class="form-label small">Data Source</label>
                    <select class="form-select form-select-sm input-source-select"
                            onchange="handleSourceChange(this, ${id}); updateJsonPreview()">
                        ${sourceOptionsHtml}
                        <option value="__custom__">Custom value...</option>
                    </select>
                </div>
            </div>
            <div class="row mt-2">
                <div class="col-md-6">
                    <input type="text" class="form-control form-control-sm input-source-custom"
                           value="${currentSourceValue}"
                           placeholder="Source (employee.field) or default value"
                           onchange="updateJsonPreview()"
                           style="${currentSourceValue && !availableSources.some(s => s.value === currentSourceValue) ? '' : 'display:none'}">
                </div>
                <div class="col-md-6">
                    <input type="text" class="form-control form-control-sm input-description"
                           value="${data?.description || ''}"
                           placeholder="Description (optional)"
                           onchange="updateJsonPreview()">
                </div>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', html);

    // Set the select value if it matches an available source
    const selectEl = document.querySelector(`#input-${id} .input-source-select`);
    if (currentSourceValue) {
        const matchingSource = availableSources.some(s => s.value === currentSourceValue);
        if (matchingSource) {
            selectEl.value = currentSourceValue;
        } else {
            selectEl.value = '__custom__';
            document.querySelector(`#input-${id} .input-source-custom`).style.display = '';
        }
    }

    updateJsonPreview();
}

function handleSourceChange(selectEl, inputId) {
    const customInput = document.querySelector(`#input-${inputId} .input-source-custom`);
    if (selectEl.value === '__custom__') {
        customInput.style.display = '';
        customInput.focus();
    } else if (selectEl.value === '') {
        customInput.style.display = 'none';
        customInput.value = '';
    } else {
        customInput.style.display = 'none';
        customInput.value = selectEl.value;
    }
}

function removeInput(id) {
    document.getElementById(`input-${id}`).remove();
    updateJsonPreview();
}

function moveInputUp(id) {
    const element = document.getElementById(`input-${id}`);
    const prev = element.previousElementSibling;
    if (prev) {
        element.parentNode.insertBefore(element, prev);
        updateJsonPreview();
    }
}

function moveInputDown(id) {
    const element = document.getElementById(`input-${id}`);
    const next = element.nextElementSibling;
    if (next) {
        element.parentNode.insertBefore(next, element);
        updateJsonPreview();
    }
}

function addStep(type, data = null) {
    const container = document.getElementById('steps-container');
    const id = stepCounter++;

    let typeHtml = '';
    let typeBadgeClass = '';

    switch(type) {
        case 'calculation':
            typeBadgeClass = 'bg-primary';
            typeHtml = `
                <div class="mb-2">
                    <label class="form-label small">Fórmula</label>
                    <input type="text" class="form-control form-control-sm step-formula"
                           value="${data?.formula || ''}"
                           placeholder="Ej: salario_mensual * 12"
                           onchange="updateJsonPreview()">
                </div>
            `;
            break;
        case 'conditional':
            typeBadgeClass = 'bg-warning text-dark';
            typeHtml = `
                <div class="mb-2">
                    <label class="form-label small">Condición</label>
                    <div class="row g-2">
                        <div class="col-4">
                            <input type="text" class="form-control form-control-sm step-cond-left"
                                   value="${data?.condition?.left || ''}" placeholder="Variable"
                                   onchange="updateJsonPreview()">
                        </div>
                        <div class="col-2">
                            <select class="form-select form-select-sm step-cond-op" onchange="updateJsonPreview()">
                                <option value=">" ${ data?.condition?.operator === '>' ? 'selected' : '' }>&gt;</option>
                                <option value=">=" ${ data?.condition?.operator === '>=' ? 'selected' : '' }>&gt;=</option>
                                <option value="<" ${ data?.condition?.operator === '<' ? 'selected' : '' }>&lt;</option>
                                <option value="<=" ${ data?.condition?.operator === '<=' ? 'selected' : '' }>&lt;=</option>
                                <option value="==" ${ data?.condition?.operator === '==' ? 'selected' : '' }>==</option>
                                <option value="!=" ${ data?.condition?.operator === '!=' ? 'selected' : '' }>!=</option>
                            </select>
                        </div>
                        <div class="col-4">
                            <input type="text" class="form-control form-control-sm step-cond-right"
                                   value="${data?.condition?.right || ''}" placeholder="Valor"
                                   onchange="updateJsonPreview()">
                        </div>
                    </div>
                </div>
                <div class="row g-2">
                    <div class="col-6">
                        <label class="form-label small">Si verdadero</label>
                        <input type="text" class="form-control form-control-sm step-if-true"
                               value="${data?.if_true || ''}" placeholder="Fórmula si cumple"
                               onchange="updateJsonPreview()">
                    </div>
                    <div class="col-6">
                        <label class="form-label small">Si falso</label>
                        <input type="text" class="form-control form-control-sm step-if-false"
                               value="${data?.if_false || ''}" placeholder="Fórmula si no cumple"
                               onchange="updateJsonPreview()">
                    </div>
                </div>
            `;
            break;
        case 'tax_lookup':
            typeBadgeClass = 'bg-danger';
            typeHtml = `
                <div class="row g-2">
                    <div class="col-6">
                        <label class="form-label small">Tabla de impuestos</label>
                        <input type="text" class="form-control form-control-sm step-table"
                               value="${data?.table || ''}" placeholder="Nombre de la tabla"
                               onchange="updateJsonPreview()">
                    </div>
                    <div class="col-6">
                        <label class="form-label small">Variable de entrada</label>
                        <input type="text" class="form-control form-control-sm step-input"
                               value="${data?.input || ''}" placeholder="Variable a buscar"
                               onchange="updateJsonPreview()">
                    </div>
                </div>
            `;
            break;
        case 'assignment':
            typeBadgeClass = 'bg-info';
            typeHtml = `
                <div class="mb-2">
                    <label class="form-label small">Valor</label>
                    <input type="text" class="form-control form-control-sm step-value"
                           value="${data?.value || ''}" placeholder="Variable o valor a asignar"
                           onchange="updateJsonPreview()">
                </div>
            `;
            break;
    }

    const html = `
        <div class="step-item" id="step-${id}" data-type="${type}">
            <div class="drag-handle">
                <i class="bi bi-grip-vertical"></i>
            </div>
            <div class="reorder-buttons">
                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="moveStepUp(${id})" title="Subir">
                    <i class="bi bi-arrow-up"></i>
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="moveStepDown(${id})" title="Bajar">
                    <i class="bi bi-arrow-down"></i>
                </button>
            </div>
            <button type="button" class="btn btn-danger btn-sm remove-btn" onclick="removeStep(${id})">
                <i class="bi bi-x"></i>
            </button>
            <div class="d-flex align-items-center mb-2">
                <span class="badge ${typeBadgeClass} step-type-badge me-2">${type}</span>
                <input type="text" class="form-control form-control-sm step-name"
                       value="${data?.name || ''}" placeholder="Nombre del paso"
                       style="max-width: 200px;" onchange="updateJsonPreview()">
            </div>
            ${typeHtml}
            <div class="mt-2">
                <input type="text" class="form-control form-control-sm step-description"
                       value="${data?.description || ''}" placeholder="Descripción (opcional)"
                       onchange="updateJsonPreview()">
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', html);
    updateJsonPreview();
}

function removeStep(id) {
    document.getElementById(`step-${id}`).remove();
    updateJsonPreview();
}

function moveStepUp(id) {
    const element = document.getElementById(`step-${id}`);
    const prev = element.previousElementSibling;
    if (prev) {
        element.parentNode.insertBefore(element, prev);
        updateJsonPreview();
    }
}

function moveStepDown(id) {
    const element = document.getElementById(`step-${id}`);
    const next = element.nextElementSibling;
    if (next) {
        element.parentNode.insertBefore(next, element);
        updateJsonPreview();
    }
}

function addTaxTable(name = null, brackets = null) {
    const container = document.getElementById('tax-tables-container');
    const id = tableCounter++;

    const html = `
        <div class="tax-table-item" id="table-${id}">
            <button type="button" class="btn btn-danger btn-sm remove-btn" onclick="removeTaxTable(${id})">
                <i class="bi bi-x"></i>
            </button>
            <div class="mb-3">
                <label class="form-label small">Nombre de la tabla</label>
                <input type="text" class="form-control form-control-sm table-name"
                       value="${name || ''}" placeholder="Ej: income_tax_brackets"
                       onchange="updateJsonPreview()">
            </div>
            <div class="brackets-container" id="brackets-${id}">
                <!-- Brackets will be added here -->
            </div>
            <button type="button" class="btn btn-sm btn-outline-primary mt-2" onclick="addBracket(${id})">
                <i class="bi bi-plus-lg me-1"></i>Agregar Tramo
            </button>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', html);

    // Add existing brackets
    if (brackets && brackets.length > 0) {
        brackets.forEach(bracket => addBracket(id, bracket));
    }

    updateJsonPreview();
}

function removeTaxTable(id) {
    document.getElementById(`table-${id}`).remove();
    updateJsonPreview();
}

function addBracket(tableId, data = null) {
    const container = document.getElementById(`brackets-${tableId}`);
    const html = `
        <div class="bracket-row">
            <div class="row g-2 align-items-center">
                <div class="col">
                    <input type="number" class="form-control form-control-sm bracket-min"
                           value="${data?.min ?? ''}" placeholder="Mín"
                           onchange="updateJsonPreview()">
                </div>
                <div class="col">
                    <input type="number" class="form-control form-control-sm bracket-max"
                           value="${data?.max ?? ''}" placeholder="Máx"
                           onchange="updateJsonPreview()">
                </div>
                <div class="col">
                    <input type="number" class="form-control form-control-sm bracket-rate"
                           value="${data?.rate ?? ''}" placeholder="Tasa" step="0.01"
                           onchange="updateJsonPreview()">
                </div>
                <div class="col">
                    <input type="number" class="form-control form-control-sm bracket-fixed"
                           value="${data?.fixed ?? ''}" placeholder="Fijo"
                           onchange="updateJsonPreview()">
                </div>
                <div class="col">
                    <input type="number" class="form-control form-control-sm bracket-over"
                           value="${data?.over ?? ''}" placeholder="Sobre"
                           onchange="updateJsonPreview()">
                </div>
                <div class="col-auto">
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('.bracket-row').remove(); updateJsonPreview();">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', html);
    updateJsonPreview();
}

function updateOutputSelect() {
    const select = document.getElementById('output-variable');
    const currentValue = select.value;
    select.innerHTML = '<option value="">Seleccionar variable de resultado...</option>';

    // Add all input names
    document.querySelectorAll('.input-name').forEach(input => {
        if (input.value) {
            select.innerHTML += `<option value="${input.value}">${input.value} (input)</option>`;
        }
    });

    // Add all step names
    document.querySelectorAll('.step-name').forEach(input => {
        if (input.value) {
            select.innerHTML += `<option value="${input.value}">${input.value} (step)</option>`;
        }
    });

    select.value = currentValue;
}

function collectSchemaFromEditor() {
    const newSchema = {
        meta: {
            name: document.getElementById('meta-name').value,
            reference_currency: document.getElementById('meta-reference-currency').value,
            description: document.getElementById('meta-description').value
        },
        inputs: [],
        steps: [],
        tax_tables: {},
        output: document.getElementById('output-variable').value
    };

    // Collect inputs
    document.querySelectorAll('.input-item').forEach(item => {
        const input = {
            name: item.querySelector('.input-name').value,
            type: item.querySelector('.input-type').value
        };
        // Get source from either the select dropdown or the custom input field
        const selectEl = item.querySelector('.input-source-select');
        const customEl = item.querySelector('.input-source-custom');
        let source = '';
        if (selectEl?.value && selectEl.value !== '__custom__' && selectEl.value !== '') {
            source = selectEl.value;
        } else if (customEl) {
            source = customEl.value;
        }
        if (source) {
            if (source.includes('.')) {
                input.source = source;
            } else if (!Number.isNaN(source)) {
                input.default = Number.parseFloat(source);
            } else {
                input.default = source;
            }
        }
        const desc = item.querySelector('.input-description').value;
        if (desc) input.description = desc;

        if (input.name) newSchema.inputs.push(input);
    });

    // Collect steps
    document.querySelectorAll('.step-item').forEach(item => {
        const type = item.dataset.type;
        const step = {
            name: item.querySelector('.step-name').value,
            type: type
        };

        switch(type) {
            case 'calculation':
                step.formula = item.querySelector('.step-formula').value;
                break;
            case 'conditional':
                step.condition = {
                    left: item.querySelector('.step-cond-left').value,
                    operator: item.querySelector('.step-cond-op').value,
                    right: item.querySelector('.step-cond-right').value
                };
                // Try to parse right value as number
                if (!Number.isNaN(step.condition.right)) {
                    step.condition.right = Number.parseFloat(step.condition.right);
                }
                step.if_true = item.querySelector('.step-if-true').value;
                step.if_false = item.querySelector('.step-if-false').value;
                break;
            case 'tax_lookup':
                step.table = item.querySelector('.step-table').value;
                step.input = item.querySelector('.step-input').value;
                break;
            case 'assignment':
                step.value = item.querySelector('.step-value').value;
                break;
        }

        const desc = item.querySelector('.step-description').value;
        if (desc) step.description = desc;

        if (step.name) newSchema.steps.push(step);
    });

    // Collect tax tables
    document.querySelectorAll('.tax-table-item').forEach(item => {
        const tableName = item.querySelector('.table-name').value;
        if (!tableName) return;

        const brackets = [];
        item.querySelectorAll('.bracket-row').forEach(row => {
            const bracket = {};
            const min = row.querySelector('.bracket-min').value;
            const max = row.querySelector('.bracket-max').value;
            const rate = row.querySelector('.bracket-rate').value;
            const fixed = row.querySelector('.bracket-fixed').value;
            const over = row.querySelector('.bracket-over').value;

            if (min !== '') bracket.min = Number.parseFloat(min);
            if (max !== '') bracket.max = Number.parseFloat(max);
            else bracket.max = null;
            if (rate !== '') bracket.rate = Number.parseFloat(rate);
            if (fixed !== '') bracket.fixed = Number.parseFloat(fixed);
            if (over !== '') bracket.over = Number.parseFloat(over);

            if (Object.keys(bracket).length > 0) brackets.push(bracket);
        });

        if (brackets.length > 0) {
            newSchema.tax_tables[tableName] = brackets;
        }
    });

    return newSchema;
}

function updateJsonPreview() {
    const schema = collectSchemaFromEditor();
    document.getElementById('json-preview').value = JSON.stringify(schema, null, 2);
    updateOutputSelect();
    generateTestInputs();
}

function generateTestInputs() {
    const container = document.getElementById('test-inputs-container');
    container.innerHTML = '';

    schema.inputs.forEach(input => {
        const html = `
            <div class="mb-2">
                <label class="form-label small">${input.name}</label>
                <input type="number" class="form-control form-control-sm test-input"
                       data-name="${input.name}"
                       value="${input.default || 0}" step="0.01">
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);
    });
}

function copyJson() {
    const textarea = document.getElementById('json-preview');
    navigator.clipboard.writeText(textarea.value).then(() => {
        alert('JSON copied to clipboard');
    });
}

function formatJson() {
    const textarea = document.getElementById('json-preview');
    try {
        const json = JSON.parse(textarea.value);
        textarea.value = JSON.stringify(json, null, 2);
    } catch (error) {
        alert('Invalid JSON: ' + error.message);
    }
}

function loadExample() {
    if (confirm('Load progressive tax example? This will replace the current schema.')) {
        window.schema = structuredClone(exampleSchema);
        loadSchemaToEditor();
        updateJsonPreview();
        alert('Example loaded successfully');
    }
}

async function saveSchema() {
    try {
        const schemaToSave = collectSchemaFromEditor();
        const ruleId = document.body.dataset.ruleId;

        const response = await fetch(`/calculation-rule/api/save-schema/${ruleId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ schema: schemaToSave })
        });

        const result = await response.json();

        if (result.success) {
            alert('Esquema guardado exitosamente');
        } else {
            alert('Error: ' + result.error);
        }
    } catch (e) {
        alert('Error al guardar: ' + e.message);
    }
}

async function testCalculation() {
    try {
        const testInputs = {};
        document.querySelectorAll('.test-input').forEach(input => {
            testInputs[input.dataset.name] = Number.parseFloat(input.value) || 0;
        });

        const ruleId = document.body.dataset.ruleId;

        const response = await fetch(`/calculation-rule/api/test-schema/${ruleId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                schema: collectSchemaFromEditor(),
                inputs: testInputs
            })
        });

        const result = await response.json();

        const resultDiv = document.getElementById('test-result');
        const resultContent = document.getElementById('test-result-content');

        resultDiv.style.display = 'block';

        if (result.success) {
            // Format result with 2 decimal places
            const formattedResult = formatResultWithDecimals(result.result);
            resultContent.innerHTML = JSON.stringify(formattedResult, null, 2);
            resultContent.classList.remove('text-danger');
            resultContent.classList.add('text-success');
        } else {
            resultContent.innerHTML = 'Error: ' + result.error;
            resultContent.classList.remove('text-success');
            resultContent.classList.add('text-danger');
        }
    } catch (e) {
        alert('Error al probar: ' + e.message);
    }
}

function formatResultWithDecimals(obj) {
    if (typeof obj === 'number') {
        return Number.parseFloat(obj.toFixed(2));
    } else if (typeof obj === 'object' && obj !== null) {
        if (Array.isArray(obj)) {
            return obj.map(item => formatResultWithDecimals(item));
        } else {
            const formatted = {};
            for (const key in obj) {
                formatted[key] = formatResultWithDecimals(obj[key]);
            }
            return formatted;
        }
    }
    return obj;
}

async function loadJsonFile(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Check file type
    if (!file.name.endsWith('.json')) {
        alert('Please select a valid JSON file');
        event.target.value = '';
        return;
    }

    try {
        const text = await file.text();
        let jsonData;

        // Parse JSON
        try {
            jsonData = JSON.parse(text);
        } catch (e) {
                alert('Error: The file does not contain valid JSON\n' + e.message);
            event.target.value = '';
            return;
        }

        // Validate schema structure before loading
        const validationResult = await validateJsonSchema(jsonData);

        if (!validationResult.valid) {
            alert('Validation error:\n\n' + validationResult.error);
            event.target.value = '';
            return;
        }

        // Show confirmation dialog
        if (confirm('Load this schema? This will replace the current schema.')) {
            window.schema = jsonData;
            loadSchemaToEditor();
            updateJsonPreview();
            alert('Schema loaded successfully');
        }

    } catch (e) {
        alert('Error reading file: ' + e.message);
    } finally {
        event.target.value = '';
    }
}

function validateStep(step, index) {
    if (!step.name) {
        return { valid: false, error: `Step ${index + 1} must have a 'name' field` };
    }
    if (!step.type) {
        return { valid: false, error: `Step ${index + 1} must have a 'type' field` };
    }

    const validTypes = ['calculation', 'conditional', 'tax_lookup', 'assignment'];
    if (!validTypes.includes(step.type)) {
        return {
            valid: false,
            error: `Step ${index + 1} has an invalid type: '${step.type}'. Allowed types: ${validTypes.join(', ')}`
        };
    }

    const requiredFields = {
        calculation: ['formula'],
        conditional: ['condition'],
        tax_lookup: ['table', 'input'],
        assignment: ['value']
    };
    const missingField = requiredFields[step.type].find(
        field => step[field] === undefined || step[field] === '' || step[field] === null
    );
    if (missingField) {
        return { valid: false, error: `Step '${step.name}' must have a '${missingField}' field` };
    }
    return null;
}

async function validateJsonSchema(jsonData) {
    // Basic structure validation
    if (!jsonData || typeof jsonData !== 'object') {
        return { valid: false, error: 'The schema must be a JSON object' };
    }

    // Check for required sections
    if (!jsonData.steps || !Array.isArray(jsonData.steps)) {
        return { valid: false, error: 'The schema must contain a \'steps\' section with an array of steps' };
    }

    // Validate steps structure
    for (const [index, step] of jsonData.steps.entries()) {
        const validationError = validateStep(step, index);
        if (validationError) {
            return validationError;
        }
    }

    // Validate with backend FormulaEngine
    try {
        const ruleId = document.body.dataset.ruleId;
        const response = await fetch(`/calculation-rule/api/validate-schema/${ruleId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ schema: jsonData })
        });

        const result = await response.json();

        if (!result.success) {
            return { valid: false, error: result.error };
        }

        return { valid: true };
    } catch (e) {
        // If backend validation fails, still allow if basic validation passed
        console.warn('Backend validation failed:', e);
        return { valid: true };
    }
}

// Make functions globally accessible
window.copyJson = copyJson;
window.formatJson = formatJson;
window.moveInputUp = moveInputUp;
window.moveInputDown = moveInputDown;
window.removeInput = removeInput;
window.moveStepUp = moveStepUp;
window.moveStepDown = moveStepDown;
window.removeStep = removeStep;
window.removeTaxTable = removeTaxTable;
window.addBracket = addBracket;
window.loadExample = loadExample;
window.saveSchema = saveSchema;
window.testCalculation = testCalculation;
window.loadJsonFile = loadJsonFile;
window.addInput = addInput;
window.addStep = addStep;
window.addTaxTable = addTaxTable;
window.handleSourceChange = handleSourceChange;
window.updateJsonPreview = updateJsonPreview;
