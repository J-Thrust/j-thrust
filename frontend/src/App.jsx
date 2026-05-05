import { useState } from "react";
import axios from "axios";
import "./App.css";

const API = "http://127.0.0.1:8000/api";

export default function App() {
  const [file, setFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [variants, setVariants] = useState([]);
  const [selected, setSelected] = useState(null);
  const [mapData, setMapData] = useState(null);
  const [aiExplanation, setAiExplanation] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);

  async function uploadCsv() {
    if (!file) {
      alert("Choose a CSV file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    const upload = await axios.post(`${API}/upload`, formData);
    setUploadStatus(upload.data);

    if (upload.data.status === "success") {
      const queue = await axios.get(`${API}/variants`);
      setVariants(queue.data.variants);
      setSelected(null);
      setMapData(null);
      setAiExplanation(null);
    }
  }

  async function openVariant(id) {
    const res = await axios.get(`${API}/variants/${id}`);
    const mapRes = await axios.get(`${API}/variants/${id}/map`);

    setSelected(res.data.variant);
    setMapData(mapRes.data);
    setAiExplanation(null);
  }

  async function generateAiExplanation() {
    if (!selected) {
      alert("Open a variant report first.");
      return;
    }

    setAiLoading(true);
    setAiExplanation(null);

    try {
      const res = await axios.get(`${API}/variants/${selected.variant_id}/ai-smart-v2`);
      setAiExplanation(res.data);
    } catch (err) {
      setAiExplanation({
        mode: "frontend_error",
        explanation: "The AI explanation request failed.",
        safety_warnings: [
          err.message,
          "Check that backend is running on port 8000.",
          "Check that the CSV was uploaded again after backend restart."
        ]
      });
    } finally {
      setAiLoading(false);
    }
  }

  function badgeClass(priority) {
    if (priority === "High priority") return "badge high";
    if (priority === "Medium priority") return "badge medium";
    if (priority === "Low priority") return "badge low";
    return "badge reanalysis";
  }

  return (
    <main className="app">
      <section className="hero">
        <p className="eyebrow">Local lab/research prototype</p>
        <h1>J Thrust</h1>
        <p className="subtitle">Lab-facing VUS evidence router</p>
        <div className="safety">
          J Thrust does not classify variants, determine benign/pathogenic status,
          or make medical recommendations. It only routes uncertain variants toward
          missing evidence paths for lab/research triage.
        </div>
      </section>

      <section className="card">
        <h2>1. Upload demo CSV</h2>
        <p>Upload this file:</p>
        <code>~/j-thrust/data/demo_variants.csv</code>

        <div className="uploadRow">
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setFile(e.target.files[0])}
          />
          <button onClick={uploadCsv}>Upload CSV</button>
        </div>

        {uploadStatus && (
          <div className={uploadStatus.status === "success" ? "success" : "error"}>
            <strong>Status:</strong> {uploadStatus.status}
            <br />
            <strong>Variants loaded:</strong> {uploadStatus.variant_count}
            {uploadStatus.errors?.length > 0 && (
              <ul>
                {uploadStatus.errors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      <section className="card">
        <h2>2. Ranked VUS Priority Queue</h2>

        {variants.length === 0 ? (
          <p>No variants loaded yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Variant</th>
                <th>Classification</th>
                <th>Priority</th>
                <th>Main reason</th>
                <th>Primary evidence path</th>
                <th>Primary actor</th>
                <th>Report</th>
              </tr>
            </thead>
            <tbody>
              {variants.map((v, index) => (
                <tr key={v.variant_id}>
                  <td>{index + 1}</td>
                  <td>
                    <span className="variantId">{v.variant_id}</span>
                    <br />
                    <strong>{v.gene}</strong>
                    <br />
                    {v.variant_hgvs}
                  </td>
                  <td>{v.current_classification}</td>
                  <td>
                    <span className={badgeClass(v.priority_category)}>
                      {v.priority_category}
                    </span>
                  </td>
                  <td>{v.main_reason}</td>
                  <td>{v.primary_evidence_path}</td>
                  <td>{v.primary_actor}</td>
                  <td>
                    <button onClick={() => openVariant(v.variant_id)}>
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {selected && (
        <section className="card">
          <h2>3. Single-Variant Evidence Report</h2>

          <div className="reportHeader">
            <div>
              <p className="eyebrow">Selected variant</p>
              <h3>{selected.gene} {selected.variant_hgvs}</h3>
              <p className="variantId">{selected.variant_id}</p>
              <p>{selected.condition}</p>
            </div>
            <span className={badgeClass(selected.priority_category)}>
              {selected.priority_category}
            </span>
          </div>

          <div className="grid">
            <div className="miniCard">
              <h4>Current classification snapshot</h4>
              <p>{selected.current_classification}</p>
            </div>

            <div className="miniCard">
              <h4>Primary evidence path</h4>
              <p>{selected.primary_evidence_path}</p>
            </div>

            <div className="miniCard">
              <h4>Primary actor</h4>
              <p>{selected.primary_actor}</p>
            </div>
          </div>

          <h3>Source snapshots</h3>

          <div className="grid">
            <div className="miniCard">
              <h4>ClinVar</h4>
              <p>{selected.clinvar_snapshot}</p>
            </div>

            <div className="miniCard">
              <h4>ClinGen</h4>
              <p>{selected.clingen_snapshot}</p>
            </div>

            <div className="miniCard">
              <h4>gnomAD</h4>
              <p>{selected.gnomad_snapshot}</p>
            </div>

            <div className="miniCard">
              <h4>Splice prediction</h4>
              <p>{selected.splice_prediction_snapshot}</p>
            </div>

            <div className="miniCard">
              <h4>MaveDB / functional</h4>
              <p>{selected.mavedb_snapshot}</p>
            </div>
          </div>

          <h3>Secondary evidence paths</h3>
          {selected.secondary_evidence_paths.length === 0 ? (
            <p>No secondary paths listed.</p>
          ) : (
            <ul>
              {selected.secondary_evidence_paths.map((path, i) => (
                <li key={i}>{path}</li>
              ))}
            </ul>
          )}

          <h3>Simple Evidence Map</h3>
          {mapData ? (
            <div className="mapBox">
              {mapData.nodes.map((node) => (
                <div className="mapNode" key={node.id}>
                  <span>{node.type}</span>
                  <strong>{node.label}</strong>
                </div>
              ))}
            </div>
          ) : (
            <p>No map loaded.</p>
          )}

          <h3>AI-Assisted Explanation</h3>
          <button onClick={generateAiExplanation} disabled={aiLoading}>
            {aiLoading ? "Generating..." : "Generate AI Explanation"}
          </button>

          {aiExplanation && (
            <div className="note">
              <p><strong>Mode:</strong> {aiExplanation.mode}</p>
              <p>{aiExplanation.explanation}</p>

              {aiExplanation.safety_warnings?.length > 0 && (
                <div className="error">
                  <strong>Safety warnings:</strong>
                  <ul>
                    {aiExplanation.safety_warnings.map((warning, i) => (
                      <li key={i}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <h3>Internal lab/research note</h3>
          <div className="note">
            {selected.gene} {selected.variant_hgvs} remains listed as{" "}
            {selected.current_classification} in the current demo evidence snapshot.
            The structured evidence fields suggest that{" "}
            {selected.primary_evidence_path} is the most useful immediate
            research/lab evidence path. The primary actor is{" "}
            {selected.primary_actor}. J Thrust does not reclassify this variant or
            make medical-management recommendations.
          </div>

          <h3>What J Thrust is not saying</h3>
          <ul>
            <li>J Thrust is not reclassifying this variant.</li>
            <li>J Thrust is not saying this variant is benign or pathogenic.</li>
            <li>J Thrust is not saying this variant causes cancer.</li>
            <li>J Thrust is not making patient-care recommendations.</li>
            <li>J Thrust is not replacing lab experts.</li>
          </ul>

          <div className="safety">{selected.safety_boundary}</div>
        </section>
      )}
    </main>
  );
}
