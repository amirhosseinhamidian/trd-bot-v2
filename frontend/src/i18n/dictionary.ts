export interface DashboardDictionary {
  metadata: {
    title: string;
    description: string;
  };

  language: {
    persian: string;
    english: string;
    changeLanguage: string;
  };

  navigation: {
    dashboard: string;
    datasets: string;
    experiments: string;
    walkForward: string;
  };

  hero: {
    eyebrow: string;
    title: string;
    description: string;
    scope: string;
  };

  overview: {
    datasets: string;
    experiments: string;
    walkForwardRuns: string;
    researchStage: string;
  };

  stages: {
    empty: string;
    dataAvailable: string;
    experimentsAvailable: string;
    walkForwardAvailable: string;
  };

  actions: {
    refresh: string;
    viewActivity: string;
  };

  footer: {
    researchOnly: string;
  };
}
