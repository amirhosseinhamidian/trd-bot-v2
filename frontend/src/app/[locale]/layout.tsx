import type { Metadata } from 'next';
import localFont from 'next/font/local';
import { notFound } from 'next/navigation';
import type { ReactNode } from 'react';

import DashboardShell from '@/components/layout/dashboard-shell';

import '../globals.css';

const vazirmatn = localFont({
  src: '../fonts/Vazirmatn[wght].ttf',
  variable: '--font-vazirmatn',
  weight: '100 900',
  style: 'normal',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'TRD Research',
  description: 'Research, backtesting, and paper-analysis dashboard',
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
    <html lang={locale} dir={locale === 'fa' ? 'rtl' : 'ltr'}>
      <body className={`${vazirmatn.variable} font-sans antialiased`}>
        <DashboardShell locale={locale}>{children}</DashboardShell>
      </body>
    </html>
  );
}
