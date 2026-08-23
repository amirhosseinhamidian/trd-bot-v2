import type { DashboardDictionary } from '@/i18n/dictionary';

const en: DashboardDictionary = {
  metadata: {
    title: 'TRD BOT v2 | Market Research Dashboard',
    description: 'Historical research, backtesting, and paper-analysis dashboard.',
  },

  language: {
    persian: 'فارسی',
    english: 'English',
    changeLanguage: 'Change language',
  },

  navigation: {
    dashboard: 'Dashboard',
    datasets: 'Datasets',
    experiments: 'Experiments',
    walkForward: 'Walk-forward',
  },

  hero: {
    eyebrow: 'Historical research dashboard',
    title: 'Measurable and reproducible market research',
    description:
      'Review datasets, strategy experiments, and walk-forward results in a research environment.',
    scope: 'Historical Research / Paper Analysis Only',
  },

  overview: {
    datasets: 'Datasets',
    experiments: 'Experiments',
    walkForwardRuns: 'Walk-forward runs',
    researchStage: 'Research stage',
  },

  stages: {
    empty: 'No data',
    dataAvailable: 'Data available',
    experimentsAvailable: 'Experiments available',
    walkForwardAvailable: 'Walk-forward available',
  },

  actions: {
    refresh: 'Refresh',
    viewActivity: 'View activity',
  },

  footer: {
    researchOnly:
      'The current system is designed only for historical research, backtesting, and paper analysis.',
  },
};

export default en;
