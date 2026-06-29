import { Card, CardContent, Typography } from "@mui/material";

export function ComingSoonPage({ title }: { title: string }) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h5" fontWeight={700} gutterBottom>
          {title}
        </Typography>
        <Typography color="text.secondary">This area is not wired up yet. Check back in a later release.</Typography>
      </CardContent>
    </Card>
  );
}
