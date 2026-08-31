import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';

export type StrategyWorkspaceCopy = {
  catalog: {
    eyebrow: string;
    title: string;
    description: string;
    total: string;
    version: string;
    parameters: string;
    viewDetails: string;
    emptyTitle: string;
    emptyDescription: string;
  };
  detail: {
    back: string;
    eyebrow: string;
    identifier: string;
    version: string;
    parameterCount: string;
    metadataTitle: string;
    metadataDescription: string;
    parametersTitle: string;
    parametersDescription: string;
    kind: string;
    defaultValue: string;
    minimum: string;
    maximum: string;
    noMinimum: string;
    noMaximum: string;
    noParameters: string;
    kinds: {
      integer: string;
      decimal: string;
    };
    launchTitle: string;
    launchDescription: string;
    experimentAction: string;
    walkForwardAction: string;
    unavailableTitle: string;
    unavailableDescription: string;
    registryTitle: string;
    registryDescription: string;
  };
};

const copies: Record<DashboardLocale, StrategyWorkspaceCopy> = {
  fa: {
    catalog: {
      eyebrow: 'Strategy workspace',
      title: 'استراتژی‌های پژوهشی',
      description:
        'تعریف‌های نسخه‌بندی‌شده Strategy را که Backend برای پژوهش تاریخی ثبت کرده است بررسی کنید.',
      total: 'تعداد Strategy',
      version: 'نسخه',
      parameters: 'پارامترها',
      viewDetails: 'مشاهده جزئیات Strategy',
      emptyTitle: 'Strategy ثبت‌شده‌ای وجود ندارد',
      emptyDescription: 'Backend در حال حاضر metadata هیچ Strategy پژوهشی را ارائه نمی‌کند.',
    },
    detail: {
      back: 'بازگشت به Strategyها',
      eyebrow: 'Versioned research strategy',
      identifier: 'شناسه Strategy',
      version: 'نسخه',
      parameterCount: 'تعداد پارامترها',
      metadataTitle: 'قرارداد Strategy',
      metadataDescription: 'هویت و توضیح canonical ثبت‌شده در Strategy Registry',
      parametersTitle: 'پارامترهای Strategy',
      parametersDescription: 'مقادیر پیش‌فرض و محدودیت‌های عددی ارائه‌شده توسط metadata نسخه فعلی',
      kind: 'نوع',
      defaultValue: 'مقدار پیش‌فرض',
      minimum: 'حداقل',
      maximum: 'حداکثر',
      noMinimum: 'بدون حداقل ثبت‌شده',
      noMaximum: 'بدون حداکثر ثبت‌شده',
      noParameters: 'این نسخه پارامتر قابل تنظیمی در metadata ثبت نکرده است.',
      kinds: {
        integer: 'عدد صحیح',
        decimal: 'عدد اعشاری',
      },
      launchTitle: 'شروع پژوهش',
      launchDescription:
        'این نسخه را مستقیماً در یک اجرای تاریخی Experiment یا Walk-forward انتخاب کنید.',
      experimentAction: 'شروع Experiment با این Strategy',
      walkForwardAction: 'شروع Walk-forward با این Strategy',
      unavailableTitle: 'اجرای مستقیم این نسخه در دسترس نیست',
      unavailableDescription:
        'Metadata این Strategy قابل مشاهده است، اما frontend برای این name/version قرارداد اجرای پژوهشی ثبت‌شده‌ای ندارد.',
      registryTitle: 'مدیریت نسخه‌ای',
      registryDescription:
        'Strategyهای این Workspace تعریف‌های خواندنی و نسخه‌بندی‌شده Backend هستند. تغییر پارامترها هنگام اجرای پژوهش انجام می‌شود و این صفحه خود تعریف Registry را ویرایش نمی‌کند.',
    },
  },
  en: {
    catalog: {
      eyebrow: 'Strategy workspace',
      title: 'Research strategies',
      description:
        'Inspect versioned strategy definitions registered by the backend for historical research.',
      total: 'Strategies',
      version: 'Version',
      parameters: 'Parameters',
      viewDetails: 'View strategy details',
      emptyTitle: 'No registered strategies',
      emptyDescription: 'The backend is not currently exposing metadata for any research strategy.',
    },
    detail: {
      back: 'Back to strategies',
      eyebrow: 'Versioned research strategy',
      identifier: 'Strategy identifier',
      version: 'Version',
      parameterCount: 'Parameters',
      metadataTitle: 'Strategy contract',
      metadataDescription: 'Canonical identity and description registered in the Strategy Registry',
      parametersTitle: 'Strategy parameters',
      parametersDescription:
        'Defaults and numeric constraints published by metadata for this exact version',
      kind: 'Kind',
      defaultValue: 'Default value',
      minimum: 'Minimum',
      maximum: 'Maximum',
      noMinimum: 'No recorded minimum',
      noMaximum: 'No recorded maximum',
      noParameters: 'This version does not publish any configurable parameters in metadata.',
      kinds: {
        integer: 'Integer',
        decimal: 'Decimal',
      },
      launchTitle: 'Launch research',
      launchDescription:
        'Open a historical Experiment or Walk-forward run with this exact strategy preselected.',
      experimentAction: 'Start Experiment with this strategy',
      walkForwardAction: 'Start Walk-forward with this strategy',
      unavailableTitle: 'Direct execution is unavailable for this version',
      unavailableDescription:
        'This strategy metadata remains inspectable, but the frontend has no registered research execution contract for this name/version.',
      registryTitle: 'Versioned management',
      registryDescription:
        'Strategies in this workspace are read-only, versioned backend definitions. Parameter choices belong to individual research runs; this page does not mutate the Registry definition.',
    },
  },
};

export function getStrategyWorkspaceCopy(locale: DashboardLocale): StrategyWorkspaceCopy {
  return copies[locale];
}
