import { Box, Typography } from "@mui/material";
import { BrandLogo } from "../components/BrandLogo";
import { FirmSignInCard } from "../components/FirmSignInCard";

/** Dedicated firm login route; primary entry is the home page sign-in section. */
export function LoginPage() {
  return (
    <Box maxWidth={440} mx="auto" py={8} px={2}>
      <Box mb={3}>
        <BrandLogo to="/" height={40} />
      </Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Sign in
      </Typography>
      <FirmSignInCard title="Sign in" />
    </Box>
  );
}
