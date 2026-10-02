import { describe, it, expect } from "vitest";
import { avacGrado, avacCourseUrl, GRADO_VIGENTE } from "./avac";

describe("avac", () => {
  it("deriva el grado del período", () => {
    expect(avacGrado("P69")).toBe("69");
    expect(avacGrado("P68")).toBe("68");
    expect(avacGrado("67")).toBe("67");
  });

  it("usa el grado vigente cuando no hay período", () => {
    expect(avacGrado("")).toBe(GRADO_VIGENTE);
    expect(avacGrado(null)).toBe(GRADO_VIGENTE);
    expect(avacGrado(undefined)).toBe(GRADO_VIGENTE);
  });

  it("arma la URL del curso con el grado del período", () => {
    expect(avacCourseUrl("411719", "P69")).toBe(
      "https://avac.ups.edu.ec/grado69/course/search.php?areaids=core_course-course&q=411719"
    );
  });

  it("sin período cae al grado vigente", () => {
    expect(avacCourseUrl("411719")).toBe(
      `https://avac.ups.edu.ec/grado${GRADO_VIGENTE}/course/search.php?areaids=core_course-course&q=411719`
    );
  });
});
