import { Card, CardContent, CardHeader, Skeleton } from '@/components/ui';

export default function DatasetDetailLoading() {
  return (
    <div className="space-y-8" aria-busy="true">
      <section className="space-y-4">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-48" />
        <Skeleton className="h-10 w-80 max-w-full" />
      </section>

      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-96 max-w-full" />
        </CardHeader>

        <CardContent className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-24" />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-80 max-w-full" />
        </CardHeader>

        <CardContent className="space-y-3">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full" />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
