const DefenseText = ({ text }) => {
  const highlightedText = String(text || "").replace(
    /(\d+%|\$[\d,]+|₹[\d,]+|\d+x|\d+\.\d+)/g,
    '<span class="font-bold text-blue-400">$1</span>'
  );

  return (
    <div
      className="text-slate-300 leading-relaxed"
      dangerouslySetInnerHTML={{ __html: highlightedText }}
    />
  );
};

export default DefenseText;
