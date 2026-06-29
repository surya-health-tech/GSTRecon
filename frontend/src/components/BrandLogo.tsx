import { Box } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { BRAND_LOGO_SRC, BRAND_NAME } from "../brand";

type BrandLogoProps = {
  to?: string;
  /** Inline / toolbar logo height (when `fill` is false). */
  height?: number;
  collapsed?: boolean;
  /** Fill the sidebar header band. */
  fill?: boolean;
};

export function BrandLogo({ to = "/app", height = 44, collapsed = false, fill = false }: BrandLogoProps) {
  const content = (
    <Box
      component="img"
      src={BRAND_LOGO_SRC}
      alt={BRAND_NAME}
      sx={
        fill
          ? {
              width: "100%",
              height: collapsed ? 48 : 52,
              objectFit: collapsed ? "cover" : "contain",
              objectPosition: collapsed ? "left center" : "left center",
              display: "block",
            }
          : {
              height,
              width: "auto",
              maxWidth: 320,
              objectFit: "contain",
              display: "block",
            }
      }
    />
  );

  if (!to) return content;

  return (
    <Box
      component={RouterLink}
      to={to}
      sx={{
        display: "block",
        textDecoration: "none",
        color: "inherit",
        width: fill ? "100%" : undefined,
      }}
    >
      {content}
    </Box>
  );
}
