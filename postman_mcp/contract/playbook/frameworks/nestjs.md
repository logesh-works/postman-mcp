# NestJS discovery guide

**Registration signals:** `@Controller('prefix')` on a class, with `@Get(...)`,
`@Post(...)`, `@Put(...)`, `@Patch(...)`, `@Delete(...)` on its methods (path arg
optional — absence means the controller's own prefix with no suffix).

**Mount chain:** the app-level global prefix from `app.setGlobalPrefix('api')` in
`main.ts`, plus any module-level `RouterModule.register([...])` nesting. A controller's
full path is `globalPrefix + moduleRoute + controllerPrefix + methodPath`.

**Request body:** `@Body() dto: CreateXDto` — cite the `class CreateXDto` definition,
walking its full field set (careful with brace-depth when the class has decorator
arguments that are themselves object literals — don't stop at the first `}`).

**Auth:** `@UseGuards(AuthGuard)` (or a named guard) on the method or class.

**Responses:** the method's return-type annotation if it's a DTO class, or
`@ApiResponse`/`@HttpCode` decorators when present.
