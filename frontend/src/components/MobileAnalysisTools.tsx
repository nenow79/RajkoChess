import type { ReactNode } from "react";

export type MobileToolTab = "source" | "explorer" | "engine";

interface MobileAnalysisToolsProps {
  activeTab: MobileToolTab;
  onTabChange: (tab: MobileToolTab) => void;
  source: ReactNode;
  explorer: ReactNode;
  engine: ReactNode;
}

const tabs: Array<{ id: MobileToolTab; label: string }> = [
  { id: "source", label: "Partia" },
  { id: "explorer", label: "Explorer" },
  { id: "engine", label: "Silnik" },
];

export default function MobileAnalysisTools({ activeTab, onTabChange, source, explorer, engine }: MobileAnalysisToolsProps) {
  return (
    <section className="mobile-analysis-tools" aria-label="Narzędzia analizy">
      <div className="mobile-analysis-tabs" role="tablist" aria-label="Narzędzia analizy">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={activeTab === tab.id ? "active" : ""}
            onClick={() => onTabChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="mobile-analysis-tab-content" role="tabpanel">
        {activeTab === "source" ? source : activeTab === "explorer" ? explorer : engine}
      </div>
    </section>
  );
}
