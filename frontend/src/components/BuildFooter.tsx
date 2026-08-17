const buildDate = new Date(__BUILD_TIMESTAMP__);
const formattedBuildDate = Number.isNaN(buildDate.getTime())
  ? __BUILD_TIMESTAMP__
  : new Intl.DateTimeFormat("pl-PL", {
      dateStyle: "short",
      timeStyle: "medium",
    }).format(buildDate);

export default function BuildFooter() {
  return (
    <footer className="build-footer" title={__BUILD_TIMESTAMP__}>
      Ostatni build: <time dateTime={__BUILD_TIMESTAMP__}>{formattedBuildDate}</time>
    </footer>
  );
}
