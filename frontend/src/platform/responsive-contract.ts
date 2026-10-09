export type ResponsiveViewportMode = 'mobile' | 'tablet' | 'desktop' | 'wide';

export type ResponsiveNavigationMode = 'bottom-navigation' | 'tablet-drawer' | 'fixed-sidebar';

export type ResponsiveViewportContract = {
  contentGutter: 16 | 24 | 32;
  mode: ResponsiveViewportMode;
  navigation: ResponsiveNavigationMode;
  width: 360 | 390 | 768 | 1024 | 1440;
};

export const P6_RESPONSIVE_VIEWPORTS = [
  { width: 360, mode: 'mobile', navigation: 'bottom-navigation', contentGutter: 16 },
  { width: 390, mode: 'mobile', navigation: 'bottom-navigation', contentGutter: 16 },
  { width: 768, mode: 'tablet', navigation: 'tablet-drawer', contentGutter: 24 },
  { width: 1024, mode: 'desktop', navigation: 'fixed-sidebar', contentGutter: 32 },
  { width: 1440, mode: 'wide', navigation: 'fixed-sidebar', contentGutter: 32 },
] as const satisfies readonly ResponsiveViewportContract[];

export function getResponsiveViewportMode(width: number): ResponsiveViewportMode {
  if (width < 768) {
    return 'mobile';
  }

  if (width < 1024) {
    return 'tablet';
  }

  return width < 1440 ? 'desktop' : 'wide';
}
