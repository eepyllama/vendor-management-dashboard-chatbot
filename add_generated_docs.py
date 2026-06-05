def main():
    filepath = "frontend/index.html"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update layout to grid of 3 columns on Documents page
    old_layout = '    <div class="page" id="page-docs">\n      <div class="page-header">\n        <h2>Documents</h2>\n        <button class="btn"><i class="ti ti-upload"></i> Upload to AI Knowledge Base</button>\n        <button class="btn primary"><i class="ti ti-folder-plus"></i> New Folder</button>\n      </div>\n      <div class="two-col">'
    new_layout = '    <div class="page" id="page-docs">\n      <div class="page-header">\n        <h2>Documents</h2>\n        <button class="btn"><i class="ti ti-upload"></i> Upload to AI Knowledge Base</button>\n        <button class="btn primary"><i class="ti ti-folder-plus"></i> New Folder</button>\n      </div>\n      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(320px, 1fr));gap:14px;margin-bottom:20px;">'
    
    if old_layout in content:
        content = content.replace(old_layout, new_layout, 1)
        print("1. Updated layout to grid.")
    else:
        print("ERROR: old_layout not found")

    # 2. Append the Generated Documents Card
    old_ai_kb_card = """        <div class="card">
          <div class="card-header"><i class="ti ti-folder" style="color:var(--accent2);font-size:15px"></i><span class="card-title">AI Knowledge Base</span><span style="font-size:12px;color:var(--green)">● 42 docs indexed</span></div>
          <div class="card-body">
            <table class="data-table">
              <thead><tr><th>Document</th><th>Category</th><th>Chunks</th><th>Status</th></tr></thead>
              <tbody>
                <tr><td class="col-name">HR_Policy_v3.pdf</td><td>Policy</td><td style="font-family:var(--mono)">84</td><td><span class="badge green">Indexed</span></td></tr>
                <tr><td class="col-name">Contractor_SOP.docx</td><td>SOP</td><td style="font-family:var(--mono)">61</td><td><span class="badge green">Indexed</span></td></tr>
                <tr><td class="col-name">Compliance_Guide.pdf</td><td>Compliance</td><td style="font-family:var(--mono)">102</td><td><span class="badge green">Indexed</span></td></tr>
                <tr><td class="col-name">Q1_Report_2025.xlsx</td><td>Report</td><td style="font-family:var(--mono)">38</td><td><span class="badge amber">Processing</span></td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>"""

    new_ai_kb_card = """        <div class="card">
          <div class="card-header"><i class="ti ti-folder" style="color:var(--accent2);font-size:15px"></i><span class="card-title">AI Knowledge Base</span><span style="font-size:12px;color:var(--green)">● 42 docs indexed</span></div>
          <div class="card-body">
            <table class="data-table">
              <thead><tr><th>Document</th><th>Category</th><th>Chunks</th><th>Status</th></tr></thead>
              <tbody>
                <tr><td class="col-name">HR_Policy_v3.pdf</td><td>Policy</td><td style="font-family:var(--mono)">84</td><td><span class="badge green">Indexed</span></td></tr>
                <tr><td class="col-name">Contractor_SOP.docx</td><td>SOP</td><td style="font-family:var(--mono)">61</td><td><span class="badge green">Indexed</span></td></tr>
                <tr><td class="col-name">Compliance_Guide.pdf</td><td>Compliance</td><td style="font-family:var(--mono)">102</td><td><span class="badge green">Indexed</span></td></tr>
                <tr><td class="col-name">Q1_Report_2025.xlsx</td><td>Report</td><td style="font-family:var(--mono)">38</td><td><span class="badge amber">Processing</span></td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Generated Documents Card -->
        <div class="card">
          <div class="card-header">
            <i class="ti ti-file-text" style="color:var(--accent2);font-size:15px"></i>
            <span class="card-title">Generated Documents</span>
            <span style="font-size:12px;color:var(--text3)" id="generatedDocsCountLabel">0 files</span>
          </div>
          <div class="card-body" style="max-height: 290px; overflow-y: auto;">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Type</th>
                  <th>Date</th>
                  <th style="text-align:right;">Actions</th>
                </tr>
              </thead>
              <tbody id="generatedDocsTableBody">
                <!-- Will be dynamically populated -->
              </tbody>
            </table>
          </div>
        </div>
      </div>"""

    if old_ai_kb_card in content:
        content = content.replace(old_ai_kb_card, new_ai_kb_card, 1)
        print("2. Added Generated Documents Card.")
    else:
        print("ERROR: old_ai_kb_card not found")

    # 3. Add generated docs management functions into the javascript section
    # Let's insert it before checkBackendHealth
    old_health_start = "async function checkBackendHealth() {"
    generated_docs_js = """// ============================================================
//  GENERATED DOCUMENTS MANAGEMENT
// ============================================================
function addGeneratedDoc(name, type, content) {
  const docs = JSON.parse(localStorage.getItem('vendoriq_generated_docs') || '[]');
  
  const now = new Date();
  const dateStr = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) + ', ' + now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  
  const existingIdx = docs.findIndex(d => d.name === name);
  const newDoc = {
    id: 'GD-' + Math.floor(Math.random() * 90000 + 10000),
    name: name,
    type: type,
    content: content,
    date: dateStr
  };
  
  if (existingIdx !== -1) {
    docs[existingIdx] = newDoc;
  } else {
    docs.push(newDoc);
  }
  
  localStorage.setItem('vendoriq_generated_docs', JSON.stringify(docs));
  renderGeneratedDocs();
  showToast(`Added "${name}" to Generated Documents`);
}

function renderGeneratedDocs() {
  const docs = JSON.parse(localStorage.getItem('vendoriq_generated_docs') || '[]');
  const listEl = document.getElementById('generatedDocsTableBody');
  if (!listEl) return;
  
  const countEl = document.getElementById('generatedDocsCountLabel');
  if (countEl) {
    countEl.textContent = `${docs.length} file${docs.length !== 1 ? 's' : ''}`;
  }

  if (docs.length === 0) {
    listEl.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text3);padding:24px 0;">
      <i class="ti ti-file-text" style="font-size:24px;display:block;margin-bottom:6px;color:var(--text3);"></i>
      No generated documents yet.
    </td></tr>`;
    return;
  }
  
  listEl.innerHTML = docs.map((d) => `
    <tr>
      <td class="col-name" style="cursor:pointer;color:var(--accent2);" onclick="viewGeneratedDoc('${d.id}')" title="Click to view report">${d.name}</td>
      <td><span class="badge blue">${d.type}</span></td>
      <td style="font-family:var(--mono);font-size:11px">${d.date.split(',')[0]}</td>
      <td style="text-align:right;">
        <div style="display:flex;gap:4px;justify-content:flex-end;">
          <button class="btn" onclick="viewGeneratedDoc('${d.id}')" style="padding:2px 6px;font-size:11px;" title="View Report"><i class="ti ti-eye"></i></button>
          <button class="btn" onclick="downloadGeneratedDoc('${d.id}')" style="padding:2px 6px;font-size:11px;" title="Download"><i class="ti ti-download"></i></button>
          <button class="btn" onclick="deleteGeneratedDoc('${d.id}')" style="padding:2px 6px;font-size:11px;color:var(--red);border-color:rgba(240,85,85,0.15);" title="Delete"><i class="ti ti-trash"></i></button>
        </div>
      </td>
    </tr>
  `).join('');
}

function viewGeneratedDoc(id) {
  const docs = JSON.parse(localStorage.getItem('vendoriq_generated_docs') || '[]');
  const doc = docs.find(d => d.id === id);
  if (!doc) return;
  
  navigate('reports');
  
  const panel = document.getElementById('reportOutputPanel');
  const content = document.getElementById('reportOutputContent');
  const titleEl = document.getElementById('reportOutputTitle');
  const badgeEl = document.getElementById('reportOutputBadge');
  
  titleEl.textContent = doc.name;
  badgeEl.textContent = doc.type;
  content.innerHTML = marked.parse(doc.content);
  panel.style.display = 'block';
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  
  lastGeneratedReport = doc.content;
  lastReportTitle = doc.name;
  
  showToast(`Viewing "${doc.name}"`);
}

function downloadGeneratedDoc(id) {
  const docs = JSON.parse(localStorage.getItem('vendoriq_generated_docs') || '[]');
  const doc = docs.find(d => d.id === id);
  if (!doc) return;
  const blob = new Blob([doc.content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const filename = doc.name.toLowerCase().replace(/\\s+/g, '-') + '-' + doc.id + '.txt';
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
  showToast('Downloaded document');
}

function deleteGeneratedDoc(id) {
  let docs = JSON.parse(localStorage.getItem('vendoriq_generated_docs') || '[]');
  const doc = docs.find(d => d.id === id);
  if (!doc) return;
  if (!confirm(`Are you sure you want to delete "${doc.name}" from Generated Documents?`)) return;
  
  docs = docs.filter(d => d.id !== id);
  localStorage.setItem('vendoriq_generated_docs', JSON.stringify(docs));
  renderGeneratedDocs();
  showToast('Deleted generated document');
}

"""
    if old_health_start in content:
        content = content.replace(old_health_start, generated_docs_js + old_health_start, 1)
        print("3. Injected Javascript functions.")
    else:
        print("ERROR: old_health_start not found")

    # 4. Bind addGeneratedDoc to reports and contract drafts
    # 4a. generateReport streaming success
    old_gen_stream = """    lastGeneratedReport = reportText;
    lastReportTitle = template.title;
    showToast(`${template.title} generated`);
    return;"""
    new_gen_stream = """    lastGeneratedReport = reportText;
    lastReportTitle = template.title;
    showToast(`${template.title} generated`);
    addGeneratedDoc(template.title, 'Report', reportText);
    return;"""
    if old_gen_stream in content:
        content = content.replace(old_gen_stream, new_gen_stream, 1)
        print("4a. Bound to generateReport streaming.")
    else:
        print("ERROR: generateReport streaming bind point not found")

    # 4b. generateReport fallback
    old_gen_fallback = """  lastGeneratedReport = text;
  lastReportTitle = template.title;
  content.innerHTML = marked.parse(text);
  showToast(`${template.title} generated`);
}"""
    new_gen_fallback = """  lastGeneratedReport = text;
  lastReportTitle = template.title;
  content.innerHTML = marked.parse(text);
  showToast(`${template.title} generated`);
  addGeneratedDoc(template.title, 'Report', text);
}"""
    if old_gen_fallback in content:
        content = content.replace(old_gen_fallback, new_gen_fallback, 1)
        print("4b. Bound to generateReport fallback.")
    else:
        print("ERROR: generateReport fallback bind point not found")

    # 4c. generateCustomReport streaming success
    old_custom_stream = """    lastGeneratedReport = reportText;
    lastReportTitle = template.title + ' — ' + period;
    genBtn.disabled = false;
    saveBtn.style.display = 'inline-flex';
    return;"""
    new_custom_stream = """    lastGeneratedReport = reportText;
    lastReportTitle = template.title + ' — ' + period;
    genBtn.disabled = false;
    saveBtn.style.display = 'inline-flex';
    addGeneratedDoc(lastReportTitle, 'Custom Report', reportText);
    return;"""
    if old_custom_stream in content:
        content = content.replace(old_custom_stream, new_custom_stream, 1)
        print("4c. Bound to generateCustomReport streaming.")
    else:
        print("ERROR: generateCustomReport streaming bind point not found")

    # 4d. generateCustomReport fallback
    old_custom_fallback = """  lastGeneratedReport = fallbackText;
  lastReportTitle = template.title;
  output.innerHTML = marked.parse(fallbackText);
  genBtn.disabled = false;
  saveBtn.style.display = 'inline-flex';
}"""
    new_custom_fallback = """  lastGeneratedReport = fallbackText;
  lastReportTitle = template.title;
  output.innerHTML = marked.parse(fallbackText);
  genBtn.disabled = false;
  saveBtn.style.display = 'inline-flex';
  addGeneratedDoc(template.title, 'Custom Report', fallbackText);
}"""
    if old_custom_fallback in content:
        content = content.replace(old_custom_fallback, new_custom_fallback, 1)
        print("4d. Bound to generateCustomReport fallback.")
    else:
        print("ERROR: generateCustomReport fallback bind point not found")

    # 4e. generateContractDraft streaming success
    old_draft_stream = """    }
    btn.disabled = false;
    return;
  } catch(e) {"""
    new_draft_stream = """    }
    btn.disabled = false;
    addGeneratedDoc(title + " - AI Contract Draft", 'Contract Draft', draftText);
    return;
  } catch(e) {"""
    if old_draft_stream in content:
        content = content.replace(old_draft_stream, new_draft_stream, 1)
        print("4e. Bound to generateContractDraft streaming.")
    else:
        print("ERROR: generateContractDraft streaming bind point not found")

    # 4f. generateContractDraft fallback
    old_draft_fallback = """  setTimeout(() => {
    textEl.textContent = `VENDOR MANAGEMENT AGREEMENT\\n\\nThis Agreement is entered into between ${client || '[CLIENT]'} ("Client") and ${vendor || '[VENDOR]'} ("Vendor").\\n\\n1. SCOPE OF SERVICES\\n${scope || title}\\n\\n2. TERM\\nThis Agreement shall commence on the Start Date and continue through the End Date.\\n\\n3. COMPENSATION\\nClient agrees to pay Vendor per the rates defined in Schedule A.\\n\\n4. TERMINATION\\nEither party may terminate with 30 days written notice.\\n\\n[Start the FastAPI backend server on port 8000 to enable real AI drafting]`;
    btn.disabled = false;
  }, 800);
}"""
    new_draft_fallback = """  setTimeout(() => {
    const fallbackText = `VENDOR MANAGEMENT AGREEMENT\\n\\nThis Agreement is entered into between ${client || '[CLIENT]'} ("Client") and ${vendor || '[VENDOR]'} ("Vendor").\\n\\n1. SCOPE OF SERVICES\\n${scope || title}\\n\\n2. TERM\\nThis Agreement shall commence on the Start Date and continue through the End Date.\\n\\n3. COMPENSATION\\nClient agrees to pay Vendor per the rates defined in Schedule A.\\n\\n4. TERMINATION\\nEither party may terminate with 30 days written notice.\\n\\n[Start the FastAPI backend server on port 8000 to enable real AI drafting]`;
    textEl.textContent = fallbackText;
    btn.disabled = false;
    addGeneratedDoc(title + " - AI Contract Draft", 'Contract Draft', fallbackText);
  }, 800);
}"""
    if old_draft_fallback in content:
        content = content.replace(old_draft_fallback, new_draft_fallback, 1)
        print("4f. Bound to generateContractDraft fallback.")
    else:
        print("ERROR: generateContractDraft fallback bind point not found")

    # 5. Run renderGeneratedDocs on page load
    old_onload = """  // Connect to backend services
  checkBackendHealth();
  loadBackendDocuments();
  setInterval(checkBackendHealth, 10000);
});"""
    new_onload = """  // Connect to backend services
  checkBackendHealth();
  loadBackendDocuments();
  renderGeneratedDocs();
  setInterval(checkBackendHealth, 10000);
});"""
    if old_onload in content:
        content = content.replace(old_onload, new_onload, 1)
        print("5. Added render call to page load listener.")
    else:
        print("ERROR: DomContentLoaded listener match not found")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Done integrating Generated Documents section!")

if __name__ == "__main__":
    main()
