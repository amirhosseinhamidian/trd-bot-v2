import type { Metadata } from 'next';
import Script from 'next/script';
import localFont from 'next/font/local';
import { notFound } from 'next/navigation';
import type { ReactNode } from 'react';

import DashboardShell from '@/components/layout/dashboard-shell';
import { THEME_BOOTSTRAP_SCRIPT, THEME_BOOTSTRAP_SCRIPT_ID } from '@/components/theme/theme';
import { NEXORA_TRD_BOT_BRAND_NAME, NEXORA_TRD_BOT_METADATA_DESCRIPTION } from '@/platform/brand';

import '../globals.css';

const vazirmatn = localFont({
  src: '../fonts/Vazirmatn[wght].ttf',
  variable: '--font-vazirmatn',
  weight: '100 900',
  style: 'normal',
  display: 'swap',
});

export const metadata: Metadata = {
  applicationName: NEXORA_TRD_BOT_BRAND_NAME,
  title: NEXORA_TRD_BOT_BRAND_NAME,
  description: NEXORA_TRD_BOT_METADATA_DESCRIPTION,
};

type LocaleLayoutProps = {
  children: ReactNode;
  params: Promise<{
    locale: string;
  }>;
};

export default async function LocaleLayout({ children, params }: LocaleLayoutProps) {
  const { locale } = await params;

  if (locale !== 'fa' && locale !== 'en') {
    notFound();
  }

  return (
    <html lang={locale} dir={locale === 'fa' ? 'rtl' : 'ltr'} suppressHydrationWarning>
      <body className={`${vazirmatn.variable} font-sans antialiased`}>
        <DashboardShell locale={locale}>{children}</DashboardShell>
        <Script id={THEME_BOOTSTRAP_SCRIPT_ID} strategy="beforeInteractive">
          {THEME_BOOTSTRAP_SCRIPT}
        </Script>
      </body>
    </html>
  );
}
