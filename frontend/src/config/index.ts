export const config = {
  appName: "Buddy",
  navRoutes: ["/dashboard", "/journal", "/history", "/settings"] as const,
  scoreBands: {
    productiveMin: 70,
    driftingMin: 40,
  },
  contentMaxWidth: 1280,
};
