import { useState } from "react";
import { CheckCircle, FileText, Loader, Upload } from "lucide-react";
import { uploadDocument } from "../utils/api.js";

export default function FileUpload({ onFilesUploaded }) {
  const [uploading, setUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);

  const handleFileUpload = async (event) => {
    const files = Array.from(event.target.files || []);
    if (files.length === 0) {
      return;
    }
    setUploading(true);

    const uploaded = [];
    for (const file of files) {
      try {
        const result = await uploadDocument(file);
        if (!result.error) {
          uploaded.push(result);
        }
      } catch (err) {
        // ignore upload failures for now
      }
    }

    if (uploaded.length > 0) {
      setUploadedFiles((prev) => [...prev, ...uploaded]);
      onFilesUploaded(uploaded.map((file) => file.document_id));
    }

    setUploading(false);
  };

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium mb-2">Upload Documents (optional)</label>

      <div className="border-2 border-dashed border-slate-600 rounded-lg p-4 text-center">
        <input
          type="file"
          multiple
          accept=".pdf,.xlsx,.xls,.csv,.txt"
          onChange={handleFileUpload}
          className="hidden"
          id="file-upload"
        />

        <label htmlFor="file-upload" className="cursor-pointer text-blue-400 hover:text-blue-300">
          {uploading ? (
            <Loader className="animate-spin mx-auto" size={24} />
          ) : (
            <>
              <Upload className="mx-auto mb-2" size={32} />
              Click to upload or drag files here
            </>
          )}
        </label>

        <p className="text-xs text-slate-400 mt-2">Supports: PDF, Excel, CSV, TXT</p>
      </div>

      {uploadedFiles.length > 0 && (
        <div className="mt-3 space-y-2">
          {uploadedFiles.map((file, idx) => (
            <div key={`${file.document_id}-${idx}`} className="flex items-center gap-2 text-sm bg-slate-800 rounded p-2">
              <FileText size={16} className="text-green-400" />
              <span className="flex-1">{file.filename}</span>
              <CheckCircle size={16} className="text-green-400" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
